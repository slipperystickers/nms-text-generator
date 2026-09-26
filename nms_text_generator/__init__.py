bl_info = {
    'name': 'NMS Text Generator for Blender Base Builder',
    'author': 'Kengo / Codex',
    'version': (1, 4, 0),
    'blender': (5, 1, 0),
    'location': '3D View > Sidebar > NMS Text',
    'description': 'Approved native-part lettering through NMS Base Builder; separate sidebar tab',
    'category': 'Object',
}

import importlib
import json
import math
import textwrap
import uuid
from pathlib import Path

import bpy
import bpy.utils.previews
from bpy.app.handlers import persistent
from bpy.props import BoolProperty, EnumProperty, FloatProperty, PointerProperty, StringProperty
from bpy_extras.io_utils import ExportHelper
from mathutils import Matrix, Vector

from . import layout

OWNER = 'nms_text_owner'
ROOT = 'nms_text_root'
CONFIG = 'nms_text_config'
SEQUENCE = 'nms_text_sequence'
FIELDS = ('font', 'text', 'height', 'letter_gap', 'word_gap', 'line_gap', 'alignment', 'orientation', 'face_offset', 'palette')
_previews = None
_font_items = []
_settings_lock = False
_pending_font = None

def auto_switch_toggled(settings,context):
    settings.auto_font_initialized=True

def initialize_auto_switch():
    for scene in bpy.data.scenes:
        settings=scene.nms_text_settings
        if not settings.auto_font_initialized:
            settings.auto_font=True
            settings.auto_font_initialized=True
    return None

@persistent
def initialize_auto_switch_on_load(_):
    initialize_auto_switch()

def load_settings(settings,config):
    global _settings_lock
    _settings_lock=True
    try:
        for key in FIELDS:
            setattr(settings,key,config.get(key,'FUTURE_Z') if key=='font' else config[key])
    finally:
        _settings_lock=False

def fully_selected_root(context):
    if context.mode!='OBJECT':return None
    root=selected_root(context)
    if root is None:return None
    parts=managed_parts(root)
    selected=set(context.selected_objects)
    # Never silently change multiple signs or a mixed/partial selection.
    if parts and set(parts)<=selected and selected<=set(parts)|{root}:
        return root
    return None

def font_changed(settings,context):
    global _pending_font
    if _settings_lock or not settings.auto_font or context is None:return
    root=fully_selected_root(context)
    if root is None:return
    current=json.loads(root[CONFIG]).get('font','FUTURE_Z')
    if current==settings.font:
        _pending_font=None
        return
    _pending_font=(root.name,root.get(OWNER),root[CONFIG],settings.font)
    # Defer object mutations out of the RNA update callback. An operator gives
    # the rebuild its own undo step and runs on Blender's main thread.
    if not bpy.app.timers.is_registered(apply_pending_font):
        bpy.app.timers.register(apply_pending_font,first_interval=.05)

def apply_pending_font():
    global _pending_font
    pending=_pending_font
    _pending_font=None
    if not pending or not hasattr(bpy.context.scene,'nms_text_settings'):return None
    name,owner,original,font=pending
    root=fully_selected_root(bpy.context)
    settings=bpy.context.scene.nms_text_settings
    if (root is None or root.name!=name or root.get(OWNER)!=owner or
            root[CONFIG]!=original or settings.font!=font or not settings.auto_font):return None
    try:
        bpy.ops.nms_text.change_font('EXEC_DEFAULT',font=font)
    except Exception as exc:
        settings.edit_status='Font change failed: '+str(exc)
    return None

def font_items(self,context):
    # Keep strings/tuples alive: Blender's dynamic enum callback retains references.
    return _font_items

def load_previews():
    global _previews
    _previews=bpy.utils.previews.new()
    _font_items.clear()
    for index,(key,name,path) in enumerate(layout.FONTS):
        icon=0
        preview=Path(__file__).parent/'previews'/(key.lower()+'.png')
        if preview.exists():
            icon=_previews.load(key,str(preview),'IMAGE').icon_id
        _font_items.append((key,name,name+' — native Flat Panels, A-Z and 0-9',icon,index))

def dependency_name():
    for name in bpy.context.preferences.addons.keys():
        if name == 'no_mans_sky_base_builder' or name.endswith('.no_mans_sky_base_builder'):
            return name
    return None

def get_builder():
    name = dependency_name()
    if not name:
        raise ValueError('Enable No Man\'s Sky Base Builder in Preferences > Add-ons first.')
    try:
        b = importlib.import_module(name + '.builder_v2')
    except ImportError as exc:
        raise ValueError('This Base Builder installation does not provide builder_v2.') from exc
    if not all(hasattr(b,k) for k in ('add_part','Part','BUILDER','get_asset_index')):
        raise ValueError('This Base Builder version lacks the required native-part API.')
    index = b.get_asset_index()
    missing = {'BUILDFLATPANEL'} - set(index)
    if missing:
        raise ValueError('Base Builder is missing textured native assets: ' + ', '.join(sorted(missing)))
    return b

def config_from_settings(settings):
    return {key:getattr(settings,key) for key in FIELDS}

def make_plan(config):
    return layout.plan(font=config.get('font','FUTURE_Z'),**{key:config[key] for key in ('text','height','letter_gap','word_gap','line_gap','alignment')})

def selected_root(context):
    obj = context.active_object
    while obj is not None:
        if obj.get(ROOT):
            return obj
        obj = obj.parent
    return None

def managed_parts(root):
    return sorted([obj for obj in root.children if obj.get(OWNER)==root.get(OWNER) and 'ObjectID' in obj],
                  key=lambda obj:int(obj.get(SEQUENCE,0)))

def check_matrix(matrix):
    axes = [matrix.to_3x3().col[i] for i in range(3)]
    sizes = [v.length for v in axes]
    if min(sizes) <= 1e-8 or matrix.to_3x3().determinant() <= 0:
        raise ValueError('Use positive uniform scale; mirrored or zero-scale text cannot be exported safely.')
    if max(sizes)-min(sizes) > max(sizes)*1e-5:
        raise ValueError('Text is stretched. Use the same scale on X, Y and Z.')
    if any(abs(axes[i].dot(axes[j]))/(sizes[i]*sizes[j]) > 1e-5 for i,j in ((0,1),(0,2),(1,2))):
        raise ValueError('Text contains a sheared transform; restore uniform scale.')

def placement_matrix(context, orientation):
    if orientation == 'CURSOR':
        result = context.scene.cursor.matrix.copy()
    else:
        result = Matrix.Translation(context.scene.cursor.location)
        if orientation == 'UPRIGHT':
            result = result @ Matrix.Rotation(math.pi/2,4,'X')
    check_matrix(result)
    return result

def active_palette(context, config):
    obj = context.active_object
    if config['palette']=='ACTIVE':
        if obj is None or 'ObjectID' not in obj or 'UserData' not in obj:
            raise ValueError('Select a native NMS part to copy its colour/material, or choose Default.')
        return int(obj['UserData'])
    return 0

def select_parts(context, root):
    bpy.ops.object.select_all(action='DESELECT')
    parts = managed_parts(root)
    for obj in parts:
        obj.select_set(True)
    context.view_layer.objects.active = parts[0] if parts else root

def create_text(context, config, matrix=None, user_data=None):
    """Build into a fresh collection; remove only new objects on failure."""
    b = get_builder()
    plan = make_plan(config)
    user_data = active_palette(context,config) if user_data is None else user_data
    matrix = placement_matrix(context,config['orientation']) if matrix is None else matrix.copy()
    check_matrix(matrix)
    old_selection = list(context.selected_objects)
    old_active = context.view_layer.objects.active
    before = {obj.as_pointer() for obj in bpy.data.objects}
    uid = uuid.uuid4().hex
    collection = bpy.data.collections.new('NMS Text - ' + plan['text'].replace('\n',' ')[:32])
    context.scene.collection.children.link(collection)
    collection[OWNER] = uid
    root = bpy.data.objects.new(collection.name,None)
    collection.objects.link(root)
    root.empty_display_type = 'PLAIN_AXES'
    root.empty_display_size = max(.2,config['height']*.15)
    root[ROOT] = True
    root[OWNER] = uid
    root[CONFIG] = json.dumps(config)
    root['nms_text_userdata'] = str(user_data)
    root['nms_text_part_count'] = plan['part_count']
    font_data=layout.library(config.get('font','FUTURE_Z'))
    root['nms_text_library'] = font_data['name']
    root.matrix_world = matrix
    try:
        bpy.ops.object.select_all(action='DESELECT')
        context.view_layer.objects.active = None
        scale = Matrix.Scale(plan['scale'],4)
        sequence = 0
        for glyph_index, placement in enumerate(plan['placements']):
            offset = Matrix.Translation((placement['x'],placement['y'],config['face_offset']))
            for record in font_data['glyphs'][placement['char']]:
                # add_part is the same API used by Base Builder's asset browser.
                part = b.add_part(record['ObjectID'],user_data=user_data,build_rigs=False,high_res=True)
                obj = part.object
                for old_collection in list(obj.users_collection):
                    old_collection.objects.unlink(obj)
                collection.objects.link(obj)
                obj.parent = root
                obj.matrix_parent_inverse = Matrix.Identity(4)
                obj.matrix_basis = offset @ scale @ b.Part.create_matrix_from_vectors(record['Position'],record['Up'],record['At'])
                obj[OWNER] = uid
                obj[SEQUENCE] = sequence
                obj['nms_text_character'] = placement['char']
                obj['nms_text_glyph_index'] = glyph_index
                obj['nms_text_line'] = placement['line']
                obj.select_set(False)
                context.view_layer.objects.active = None
                if not obj.data.name.startswith('NMS_HR_') or not obj.material_slots:
                    raise ValueError('Base Builder did not return the expected textured native asset.')
                sequence += 1
        context.view_layer.update()
        assert len(managed_parts(root)) == plan['part_count']
        select_parts(context,root)
        return root
    except Exception:
        # This synchronous operation creates no external state. Scope rollback
        # by the pre-call object snapshot, never by names or the whole scene.
        for obj in list(bpy.data.objects):
            if obj.as_pointer() not in before:
                bpy.data.objects.remove(obj,do_unlink=True)
        bpy.data.collections.remove(collection)
        for obj in old_selection:
            obj.select_set(True)
        context.view_layer.objects.active = old_active
        raise

def replace_text(context, root, config):
    check_matrix(root.matrix_world)
    old_parts = managed_parts(root)
    if not old_parts:
        raise ValueError('The selected text has no managed parts to replace.')
    collections = [c for c in root.users_collection if c.get(OWNER)==root.get(OWNER)]
    if len(collections)!=1:
        raise ValueError('The text collection has changed. Generate a new sign instead.')
    destination = collections[0]
    # Placement/orientation stays where the existing control is. Other fields
    # come from the panel. Original palette is retained unless copying active.
    config = dict(config)
    previous = json.loads(root[CONFIG])
    config['orientation'] = previous['orientation']
    palette = active_palette(context,config) if config['palette']=='ACTIVE' else int(root['nms_text_userdata'])
    staged = create_text(context,config,matrix=root.matrix_world,user_data=palette)
    new_parts = managed_parts(staged)
    staging_collection = list(staged.users_collection)[0]
    # Only after successful generation replace the old owned parts. Keep the
    # original control, transforms and any untagged user-added children.
    for obj in new_parts:
        local = obj.matrix_basis.copy()
        obj.parent = root
        obj.matrix_parent_inverse = Matrix.Identity(4)
        obj.matrix_basis = local
        obj[OWNER] = root[OWNER]
        destination.objects.link(obj)
        staging_collection.objects.unlink(obj)
    for obj in old_parts:
        bpy.data.objects.remove(obj,do_unlink=True)
    for key in (CONFIG,'nms_text_userdata','nms_text_part_count','nms_text_library'):
        root[key] = staged[key]
    destination.name='NMS Text - '+make_plan(config)['text'].replace('\n',' ')[:32]
    root.name=destination.name
    bpy.data.objects.remove(staged,do_unlink=True)
    bpy.data.collections.remove(staging_collection)
    context.view_layer.update()
    select_parts(context,root)
    return root

def export_data(root):
    b = get_builder()
    parts = managed_parts(root)
    if not parts:
        raise ValueError('No generated parts found.')
    bpy.context.view_layer.update()
    records=[]
    for obj in parts:
        check_matrix(obj.matrix_world)
        # Legacy 1.0 signs remain exportable until explicitly replaced.
        if obj.get('ObjectID') not in ('BUILDFLATPANEL','CUBEWALL'):
            raise ValueError('A managed part has an unexpected native item ID.')
        records.append(b.Part.deserialise_from_object(obj,b.BUILDER).serialise())
    return {'BaseVersion':5,'Objects':records}

class NMSTEXT_Settings(bpy.types.PropertyGroup):
    font: EnumProperty(name='Font',items=font_items,default=0,update=font_changed,description='Choose a font; auto-switch rebuilds a fully selected sign')
    auto_font: BoolProperty(name='Auto-switch selected text',default=True,update=auto_switch_toggled,description='Changing Font rebuilds one fully selected sign. Manual panel edits are replaced; Ctrl-Z undoes it')
    auto_font_initialized: BoolProperty(default=False,options={'HIDDEN'})
    edit_status: StringProperty(options={'SKIP_SAVE'})
    text: StringProperty(name='Text',default='CCB',maxlen=layout.MAX_INPUT,description='A-Z and 0-9. Lowercase converts to uppercase. Type \\n for another line')
    height: FloatProperty(name='Letter height',default=5,min=.05,max=10000,unit='LENGTH')
    letter_gap: FloatProperty(name='Letter gap',default=1,min=0,max=10000,unit='LENGTH')
    word_gap: FloatProperty(name='Space width',default=3,min=.05,max=10000,unit='LENGTH')
    line_gap: FloatProperty(name='Line gap',default=1.5,min=0,max=10000,unit='LENGTH')
    face_offset: FloatProperty(name='Face offset',default=.01,min=-1000,max=1000,unit='LENGTH',description='Distance in front of the 3D Cursor plane; rear geometry is intended to be buried')
    alignment: EnumProperty(name='Alignment',items=[('LEFT','Left','Baseline starts at the cursor'),('CENTER','Center','Each line centered on the cursor'),('RIGHT','Right','Each line ends at the cursor')],default='LEFT')
    orientation: EnumProperty(name='Orientation',items=[('FLAT','Flat (XY)','Front faces +Z'),('UPRIGHT','Upright (XZ)','Front faces -Y'),('CURSOR','3D Cursor rotation','Use the full rotation of the 3D Cursor')],default='FLAT')
    palette: EnumProperty(name='Colour / material',items=[('DEFAULT','Default / keep on replace','Native default for new text; preserve current palette when replacing'),('ACTIVE','Copy active NMS part','Copy the selected part\'s UserData palette and material finish')],default='DEFAULT')

class NMSTEXT_OT_generate(bpy.types.Operator):
    bl_idname='nms_text.generate'
    bl_label='Generate New Text'
    bl_description='Create a new text collection at the 3D Cursor; never replaces existing objects'
    bl_options={'REGISTER','UNDO'}
    @classmethod
    def poll(cls,context):
        return context.mode=='OBJECT'
    def execute(self,context):
        try:
            root=create_text(context,config_from_settings(context.scene.nms_text_settings))
            self.report({'INFO'},f"Created {root['nms_text_part_count']} native parts")
            return {'FINISHED'}
        except Exception as exc:
            self.report({'ERROR'},str(exc))
            return {'CANCELLED'}

class NMSTEXT_OT_change_font(bpy.types.Operator):
    bl_idname='nms_text.change_font'
    bl_label='Change NMS Text Font'
    bl_options={'REGISTER','UNDO'}
    font: EnumProperty(items=font_items,default=0)
    @classmethod
    def poll(cls,context):return fully_selected_root(context) is not None
    def execute(self,context):
        root=fully_selected_root(context)
        if root is None:return {'CANCELLED'}
        config=json.loads(root[CONFIG])
        config['font']=self.font
        config['palette']='DEFAULT'
        try:
            replace_text(context,root,config)
            load_settings(context.scene.nms_text_settings,config)
            context.scene.nms_text_settings.edit_status='Font updated. Ctrl-Z to undo.'
            return {'FINISHED'}
        except Exception as exc:
            load_settings(context.scene.nms_text_settings,json.loads(root[CONFIG]))
            context.scene.nms_text_settings.edit_status='Font change failed: '+str(exc)
            self.report({'ERROR'},str(exc))
            return {'CANCELLED'}

class NMSTEXT_OT_edit(bpy.types.Operator):
    bl_idname='nms_text.edit'
    bl_label='Edit NMS Text'
    bl_description='Edit the whole sign from any one of its panels; changes apply only when you confirm'
    bl_options={'REGISTER','UNDO'}
    # Independent operator settings: Cancel must not change the sign or sidebar.
    __annotations__={key:prop.function(**{k:v for k,v in prop.keywords.items() if k!='update'})
                     for key,prop in NMSTEXT_Settings.__annotations__.items() if key in FIELDS}
    root_name: StringProperty(options={'HIDDEN'})
    owner: StringProperty(options={'HIDDEN'})
    @classmethod
    def poll(cls,context):return context.mode=='OBJECT' and selected_root(context) is not None
    def invoke(self,context,event):
        root=selected_root(context)
        if root is None:
            self.report({'ERROR'},'Select a panel belonging to generated NMS text first.')
            return {'CANCELLED'}
        self.root_name=root.name
        self.owner=root.get(OWNER)
        config=json.loads(root[CONFIG])
        config.setdefault('font','FUTURE_Z')
        config['palette']='DEFAULT'
        for key in FIELDS:setattr(self,key,config[key])
        return context.window_manager.invoke_props_dialog(self,width=420)
    def draw(self,context):
        ui=self.layout
        ui.prop(self,'text')
        ui.prop(self,'font')
        ui.template_icon_view(self,'font',show_labels=True,scale=6,scale_popup=7)
        for key in ('height','alignment','letter_gap','word_gap','line_gap','face_offset','palette'):
            ui.prop(self,key)
        try:ui.label(text=f"{make_plan(config_from_settings(self))['part_count']:,} native panels")
        except ValueError as exc:ui.label(text=str(exc),icon='ERROR')
        ui.label(text='Keeps sign position and rotation.')
        ui.label(text='Rebuild replaces manual panel edits. Ctrl-Z to undo.')
    def execute(self,context):
        if not self.root_name:
            # Some menu callers use EXEC_DEFAULT. Initialize and open the dialog
            # instead of attempting a rebuild with empty target identifiers.
            return self.invoke(context,None)
        root=bpy.data.objects.get(self.root_name)
        if root is None or not root.get(ROOT) or root.get(OWNER)!=self.owner:
            self.report({'ERROR'},'The original text group is no longer available.')
            return {'CANCELLED'}
        try:
            config=config_from_settings(self)
            replace_text(context,root,config)
            load_settings(context.scene.nms_text_settings,json.loads(root[CONFIG]))
            self.root_name=root.name
            self.report({'INFO'},'NMS text updated')
            return {'FINISHED'}
        except Exception as exc:
            self.report({'ERROR'},str(exc))
            return {'CANCELLED'}

def text_context_menu(self,context):
    if NMSTEXT_OT_edit.poll(context):
        self.layout.separator()
        row=self.layout.row()
        row.operator_context='INVOKE_DEFAULT'
        row.operator('nms_text.edit',icon='FONT_DATA')

class NMSTEXT_OT_replace(bpy.types.Operator):
    bl_idname='nms_text.replace'
    bl_label='Replace Selected Text'
    bl_description='Rebuild this generated sign with the panel settings; manual edits to its generated parts are replaced. Other signs are untouched'
    bl_options={'REGISTER','UNDO'}
    @classmethod
    def poll(cls,context):
        return context.mode=='OBJECT' and selected_root(context) is not None
    def invoke(self,context,event):
        return context.window_manager.invoke_confirm(self,event)
    def execute(self,context):
        try:
            root=replace_text(context,selected_root(context),config_from_settings(context.scene.nms_text_settings))
            self.report({'INFO'},f"Replaced selected text: {root['nms_text_part_count']} parts")
            return {'FINISHED'}
        except Exception as exc:
            self.report({'ERROR'},str(exc))
            return {'CANCELLED'}

class NMSTEXT_OT_load(bpy.types.Operator):
    bl_idname='nms_text.load_settings'
    bl_label='Load Selected Text Settings'
    bl_options={'UNDO'}
    @classmethod
    def poll(cls,context):
        return selected_root(context) is not None
    def execute(self,context):
        config=json.loads(selected_root(context)[CONFIG])
        config.setdefault('font','FUTURE_Z')
        load_settings(context.scene.nms_text_settings,config)
        return {'FINISHED'}

class NMSTEXT_OT_select(bpy.types.Operator):
    bl_idname='nms_text.select'
    bl_label='Select Text'
    bl_options={'UNDO'}
    target: EnumProperty(items=[('PARTS','Parts','Select native parts for Base Builder palette and tools'),('CONTROL','Control','Select the parent control to move/rotate/scale the whole sign')])
    @classmethod
    def poll(cls,context):
        return context.mode=='OBJECT' and selected_root(context) is not None
    def execute(self,context):
        root=selected_root(context)
        if self.target=='PARTS':
            select_parts(context,root)
        else:
            bpy.ops.object.select_all(action='DESELECT')
            root.select_set(True)
            context.view_layer.objects.active=root
        return {'FINISHED'}

class NMSTEXT_OT_export(bpy.types.Operator,ExportHelper):
    bl_idname='nms_text.export_json'
    bl_label='Export Selected Text JSON'
    bl_description='Export only this text\'s native parts, including their current world transforms and colours'
    filename_ext='.json'
    filter_glob: StringProperty(default='*.json',options={'HIDDEN'})
    @classmethod
    def poll(cls,context):
        return context.mode=='OBJECT' and selected_root(context) is not None
    def execute(self,context):
        try:
            payload=export_data(selected_root(context))
            Path(self.filepath).write_text(json.dumps(payload,indent=2),encoding='utf-8')
            self.report({'INFO'},f"Exported {len(payload['Objects'])} native parts")
            return {'FINISHED'}
        except Exception as exc:
            self.report({'ERROR'},str(exc))
            return {'CANCELLED'}

class NMSTEXT_PT_panel(bpy.types.Panel):
    bl_label='NMS Text Generator'
    bl_idname='NMSTEXT_PT_panel'
    bl_space_type='VIEW_3D'
    bl_region_type='UI'
    bl_category='NMS Text'
    def draw(self,context):
        ui=self.layout
        settings=context.scene.nms_text_settings
        if not dependency_name():
            box=ui.box()
            box.alert=True
            box.label(text='Enable NMS Base Builder first.',icon='ERROR')
        ui.label(text='Flat Panels only - v1.4.0')
        ui.prop(settings,'auto_font')
        ui.prop(settings,'font')
        ui.template_icon_view(settings,'font',show_labels=True,scale=6.0,scale_popup=7.0)
        if settings.auto_font and fully_selected_root(context):
            ui.label(text='Font changes rebuild this selected sign.',icon='INFO')
        if settings.edit_status:
            for line in textwrap.wrap(settings.edit_status,42):ui.label(text=line)
        ui.prop(settings,'text')
        ui.label(text='A-Z, 0-9; type \\n for a new line',icon='INFO')
        ui.prop(settings,'height')
        ui.prop(settings,'alignment',expand=True)
        row=ui.row(align=True)
        row.prop(settings,'letter_gap')
        row.prop(settings,'word_gap')
        ui.prop(settings,'line_gap')
        ui.prop(settings,'orientation')
        ui.prop(settings,'face_offset')
        ui.prop(settings,'palette')
        valid=True
        try:
            preview=make_plan(config_from_settings(settings))
            ui.label(text=f"{preview['part_count']:,} parts / {preview['character_count']} characters",icon='MESH_CUBE')
            ui.label(text=f"Library: up to {layout.library(settings.font)['max_parts_per_character']} panels per character")
        except ValueError as exc:
            valid=False
            box=ui.box()
            box.alert=True
            for index,line in enumerate(textwrap.wrap(str(exc),width=42)):
                box.label(text=line,icon='ERROR' if index==0 else 'NONE')
        row=ui.row()
        row.enabled=valid and bool(dependency_name()) and context.mode=='OBJECT'
        row.operator('nms_text.generate',icon='ADD')
        root=selected_root(context)
        if root:
            box=ui.box()
            box.label(text=root.name,icon='OUTLINER_COLLECTION')
            row=box.row()
            row.operator_context='INVOKE_DEFAULT'
            row.operator('nms_text.edit',icon='FONT_DATA')
            box.operator('nms_text.load_settings',icon='IMPORT')
            row=box.row()
            row.enabled=valid and bool(dependency_name())
            row.operator('nms_text.replace',icon='FILE_REFRESH')
            row=box.row(align=True)
            row.operator('nms_text.select',text='Select Parts').target='PARTS'
            row.operator('nms_text.select',text='Select Control').target='CONTROL'
            box.operator('nms_text.export_json',icon='EXPORT')
        ui.label(text='Place the 3D Cursor on the mounting plane.')
        ui.label(text='Uniform scale only; rear geometry is buried.')

CLASSES=(NMSTEXT_Settings,NMSTEXT_OT_generate,NMSTEXT_OT_change_font,NMSTEXT_OT_edit,NMSTEXT_OT_replace,NMSTEXT_OT_load,NMSTEXT_OT_select,NMSTEXT_OT_export,NMSTEXT_PT_panel)

def register():
    load_previews()
    for cls in CLASSES:
        bpy.utils.register_class(cls)
    bpy.types.Scene.nms_text_settings=PointerProperty(type=NMSTEXT_Settings)
    bpy.types.VIEW3D_MT_object_context_menu.append(text_context_menu)
    bpy.app.handlers.load_post.append(initialize_auto_switch_on_load)
    bpy.app.timers.register(initialize_auto_switch,first_interval=0)

def unregister():
    global _previews,_pending_font
    _pending_font=None
    if initialize_auto_switch_on_load in bpy.app.handlers.load_post:
        bpy.app.handlers.load_post.remove(initialize_auto_switch_on_load)
    if bpy.app.timers.is_registered(initialize_auto_switch):bpy.app.timers.unregister(initialize_auto_switch)
    if bpy.app.timers.is_registered(apply_pending_font):bpy.app.timers.unregister(apply_pending_font)
    bpy.types.VIEW3D_MT_object_context_menu.remove(text_context_menu)
    del bpy.types.Scene.nms_text_settings
    for cls in reversed(CLASSES):
        bpy.utils.unregister_class(cls)
    if _previews is not None:
        bpy.utils.previews.remove(_previews)
        _previews=None
    _font_items.clear()
    layout.library.cache_clear()
