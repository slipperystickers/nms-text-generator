"""Separate SVG mode and ownership. Text collections are never SVG targets."""
import hashlib
import importlib
import json
import math
import time
import uuid
from pathlib import Path
import bpy
import bpy.utils.previews
from bpy.props import StringProperty,IntProperty,FloatProperty,EnumProperty,PointerProperty
from bpy_extras.io_utils import ImportHelper,ExportHelper
from mathutils import Matrix
from . import icon_fit,panels,svg_geometry

ROOT='nms_icon_root'
CONFIG='nms_icon_config'
_cache={}
_dirty={}
_errors=set()
_icons=None
_loading=False

def host():return importlib.import_module(__package__)
def selected(context):
    obj=context.active_object
    while obj is not None:
        if obj.get(ROOT):return obj
        obj=obj.parent
    return None

def key(settings):
    return (hashlib.sha256(settings.source.encode('utf-8')).hexdigest(),settings.accuracy,settings.max_parts)

def preview_key(k):return 'SVG_'+k[0]+f'_{k[1]}_{k[2]}'

def request_preview(scene):
    if key(scene.nms_icon_settings) in _errors:return
    _dirty.setdefault(scene.name,time.monotonic()+.1)
    if not bpy.app.timers.is_registered(refresh):bpy.app.timers.register(refresh,first_interval=.15)

def redraw():
    for window in bpy.context.window_manager.windows:
        for area in window.screen.areas:
            if area.type=='VIEW_3D':area.tag_redraw()

def changed(settings,context):
    if _loading or context is None:return
    settings.status='Updating fit preview…' if settings.source else ''
    _errors.discard(key(settings))
    scene=context.scene
    _dirty[scene.name]=time.monotonic()+.35
    if not bpy.app.timers.is_registered(refresh):bpy.app.timers.register(refresh,first_interval=.4)

def refresh():
    now=time.monotonic()
    for name,when in list(_dirty.items()):
        if when>now:continue
        _dirty.pop(name,None);scene=bpy.data.scenes.get(name)
        if scene is None or not hasattr(scene,'nms_icon_settings'):continue
        s=scene.nms_icon_settings
        if not s.source:continue
        try:analyze(s)
        except Exception as exc:s.status=str(exc);_errors.add(key(s))
    redraw()
    return .15 if _dirty else None

def analyze(settings):
    if not settings.source:raise ValueError('Import an SVG first.')
    k=key(settings)
    if k not in _cache:
        result=icon_fit.fit_svg(settings.source,settings.accuracy,settings.max_parts)
        if len(_cache)>=6:_cache.pop(next(iter(_cache)))
        _cache[k]=result
    result=_cache[k]
    # The preview is diagnostic, not an extra part in the generated collection.
    name=preview_key(k)
    if _icons is not None and name not in _icons:
        if len(_icons)>=6:
            for old in list(_icons.keys()):del _icons[old]
        icon=_icons.new(name);n=result['resolution'];icon.image_size=(n,n)
        icon.image_pixels_float=result['preview'][::-1].flatten()
    settings.preview_name=name
    if result['unfilled'] and result['part_count']>=settings.max_parts:
        settings.status='Part limit: small gaps/details remain. Raise the limit or reduce accuracy.'
    elif result['outline_relaxed']:
        settings.status='Outline simplified to fit the part budget. Raise the limit for finer curves.'
    elif result['outline_omissions']:
        settings.status='Ready. Very sharp tips are approximated.'
    else:settings.status='Ready. Outline first, then interior fill.'
    return result

FIELDS=('source','source_name','accuracy','max_parts','height','panel_type','orientation','face_offset','palette')
def config(settings):return {field:getattr(settings,field) for field in FIELDS}
def load(settings,data):
    global _loading
    _loading=True
    try:
        for field in FIELDS:setattr(settings,field,data[field])
    finally:_loading=False
    analyze(settings)

def create(context,data,matrix=None,user_data=None):
    a=host();b=a.get_builder(data['panel_type'])
    result=icon_fit.fit_svg(data['source'],data['accuracy'],data['max_parts'])
    if result['part_count']>data['max_parts']:raise ValueError('Fitted panel count exceeds the chosen limit.')
    matrix=a.placement_matrix(context,data['orientation']) if matrix is None else matrix.copy();a.check_matrix(matrix)
    user_data=a.active_palette(context,data) if user_data is None else user_data
    before={o.as_pointer() for o in bpy.data.objects};selection=list(context.selected_objects);active=context.view_layer.objects.active
    col=bpy.data.collections.new('NMS Icon - '+data['source_name'][:40]);context.scene.collection.children.link(col)
    uid=uuid.uuid4().hex;col[a.OWNER]=uid
    root=bpy.data.objects.new(col.name,None);col.objects.link(root)
    root[ROOT]=True;root[a.OWNER]=uid;root[CONFIG]=json.dumps(data)
    root['nms_text_userdata']=str(user_data);root['nms_text_part_count']=result['part_count']
    root['nms_icon_coverage']=result['coverage'];root.empty_display_size=data['height']*.12;root.matrix_world=matrix
    overall=data['height']/result['bounds'][1]
    try:
        bpy.ops.object.select_all(action='DESELECT');context.view_layer.objects.active=None
        for i,(x,y,width,angle) in enumerate(result['panels']):
            part=b.add_part(data['panel_type'],user_data=user_data,build_rigs=False,high_res=True);obj=part.object
            for old in list(obj.users_collection):old.objects.unlink(obj)
            col.objects.link(obj);obj.parent=root;obj.matrix_parent_inverse=Matrix.Identity(4)
            scale=width*overall/panels.FLAT_FOOTPRINT[1]
            rot=Matrix.Rotation(-angle,4,'Z')@Matrix.Rotation(math.pi/2,4,'X')
            pos=((x-result['bounds'][0]/2)*overall,(result['bounds'][1]/2-y)*overall,data['face_offset']-panels.FLAT_FACE_Y*scale)
            native=Matrix.Translation(pos)@rot@Matrix.Scale(scale,4)
            obj.matrix_basis=panels.from_flat_matrix(native,data['panel_type'])
            obj[a.OWNER]=uid;obj[a.SEQUENCE]=i
            if obj.get('ObjectID')!=data['panel_type'] or not obj.material_slots:raise ValueError('Base Builder did not supply native panels and materials.')
            obj.select_set(False);context.view_layer.objects.active=None
        context.view_layer.update();a.select_parts(context,root)
        return root
    except Exception:
        for obj in list(bpy.data.objects):
            if obj.as_pointer() not in before:bpy.data.objects.remove(obj,do_unlink=True)
        bpy.data.collections.remove(col)
        for obj in selection:obj.select_set(True)
        context.view_layer.objects.active=active
        raise

def replace(context,root,data):
    a=host();a.check_matrix(root.matrix_world);parts=a.managed_parts(root)
    cols=[c for c in root.users_collection if c.get(a.OWNER)==root.get(a.OWNER)]
    if not parts or len(cols)!=1:raise ValueError('The icon collection has changed. Generate a new icon instead.')
    data=dict(data);data['orientation']=json.loads(root[CONFIG])['orientation']
    user_data=a.active_palette(context,data) if data['palette']=='ACTIVE' else int(root['nms_text_userdata'])
    staged=create(context,data,root.matrix_world,user_data)
    temp=staged.users_collection[0];dest=cols[0]
    for obj in a.managed_parts(staged):
        local=obj.matrix_basis.copy();obj.parent=root;obj.matrix_parent_inverse=Matrix.Identity(4);obj.matrix_basis=local
        obj[a.OWNER]=root[a.OWNER];dest.objects.link(obj);temp.objects.unlink(obj)
    for obj in parts:bpy.data.objects.remove(obj,do_unlink=True)
    for field in (CONFIG,'nms_text_userdata','nms_text_part_count','nms_icon_coverage'):root[field]=staged[field]
    dest.name=staged.name;root.name=dest.name
    bpy.data.objects.remove(staged,do_unlink=True);bpy.data.collections.remove(temp)
    context.view_layer.update();a.select_parts(context,root);return root

class NMSICON_Settings(bpy.types.PropertyGroup):
    source: StringProperty(options={'HIDDEN'},update=changed)
    source_name: StringProperty(default='SVG icon')
    accuracy: IntProperty(name='Accuracy',default=50,min=0,max=100,subtype='PERCENTAGE',update=changed,description='Higher accuracy follows curves more closely. Part limit can force a coarser outline. Preview only; press Generate or Update to apply')
    max_parts: IntProperty(name='Part limit',default=300,min=1,max=2000,update=changed,description='Hard upper limit; excess detail is omitted, never silently creates more parts')
    height: FloatProperty(name='Icon height',default=5,min=.05,max=10000,unit='LENGTH')
    panel_type: EnumProperty(name='Panel type',items=panels.ITEMS,default=panels.NEW_DEFAULT)
    orientation: EnumProperty(name='Orientation',items=[('FLAT','Flat (XY)','Front faces +Z'),('UPRIGHT','Upright (XZ)','Front faces -Y'),('CURSOR','3D Cursor rotation','Use cursor rotation')],default='FLAT')
    face_offset: FloatProperty(name='Face offset',default=.01,min=-1000,max=1000,unit='LENGTH')
    palette: EnumProperty(name='Colour / material',items=[('DEFAULT','Default / keep on update','Use default or keep original icon material'),('ACTIVE','Copy active part','Copy colour and material from active native part')],default='DEFAULT')
    status: StringProperty(options={'SKIP_SAVE'})
    preview_name: StringProperty(options={'SKIP_SAVE'})

class NMSICON_OT_import(bpy.types.Operator,ImportHelper):
    bl_idname='nms_icon.import_svg';bl_label='Import SVG';bl_options={'UNDO'}
    filename_ext='.svg'
    filter_glob:StringProperty(default='*.svg',options={'HIDDEN'})
    def execute(self,context):
        try:
            path=Path(self.filepath)
            if path.stat().st_size>svg_geometry.MAX_BYTES:raise ValueError('SVG is larger than 1 MB. Simplify it first.')
            source=path.read_text(encoding='utf-8-sig');s=context.scene.nms_icon_settings
            # Validate/fill before replacing the previous imported source.
            data=config(s);data.update(source=source,source_name=path.stem)
            icon_fit.fit_svg(source,s.accuracy,s.max_parts)
            load(s,data);context.scene.nms_text_settings.mode='ICON'
            self.report({'INFO'},'SVG loaded. Adjust accuracy, then generate native panels.')
            return {'FINISHED'}
        except Exception as exc:self.report({'ERROR'},str(exc));return {'CANCELLED'}

class NMSICON_OT_generate(bpy.types.Operator):
    bl_idname='nms_icon.generate';bl_label='Generate New Icon';bl_options={'REGISTER','UNDO'}
    @classmethod
    def poll(cls,context):return context.mode=='OBJECT' and bool(context.scene.nms_icon_settings.source)
    def execute(self,context):
        try:
            root=create(context,config(context.scene.nms_icon_settings))
            self.report({'INFO'},f"Created {root['nms_text_part_count']} native panels")
            return {'FINISHED'}
        except Exception as exc:self.report({'ERROR'},str(exc));return {'CANCELLED'}

class NMSICON_OT_load(bpy.types.Operator):
    bl_idname='nms_icon.edit';bl_label='Edit NMS Icon / Sticker';bl_options={'UNDO'}
    bl_description='Load this icon into the sidebar, including its saved SVG. Adjust the preview and press Update Selected Icon to apply'
    @classmethod
    def poll(cls,context):return context.mode=='OBJECT' and selected(context) is not None
    def execute(self,context):
        try:
            data=json.loads(selected(context)[CONFIG]);data['palette']='DEFAULT';load(context.scene.nms_icon_settings,data)
            context.scene.nms_text_settings.mode='ICON'
            if context.area and context.area.type=='VIEW_3D':context.area.spaces.active.show_region_ui=True
            self.report({'INFO'},'Icon settings loaded in NMS Text > Icon / Sticker. Preview changes apply with Update Selected Icon.')
            return {'FINISHED'}
        except Exception as exc:self.report({'ERROR'},str(exc));return {'CANCELLED'}

class NMSICON_OT_replace(bpy.types.Operator):
    bl_idname='nms_icon.replace';bl_label='Update Selected Icon';bl_options={'REGISTER','UNDO'}
    bl_description='Replace only this icon’s generated panels, keeping its control and placement. Manual panel edits are replaced; Ctrl-Z undoes it'
    @classmethod
    def poll(cls,context):return context.mode=='OBJECT' and selected(context) is not None and bool(context.scene.nms_icon_settings.source)
    def execute(self,context):
        try:
            root=replace(context,selected(context),config(context.scene.nms_icon_settings))
            self.report({'INFO'},f"Updated icon: {root['nms_text_part_count']} panels")
            return {'FINISHED'}
        except Exception as exc:self.report({'ERROR'},str(exc));return {'CANCELLED'}

class NMSICON_OT_select(bpy.types.Operator):
    bl_idname='nms_icon.select';bl_label='Select Icon';bl_options={'UNDO'}
    target:EnumProperty(items=[('PARTS','Parts','Select all native panels'),('CONTROL','Control','Move, rotate or uniformly scale the whole icon')])
    @classmethod
    def poll(cls,context):return context.mode=='OBJECT' and selected(context) is not None
    def execute(self,context):
        root=selected(context)
        if self.target=='PARTS':host().select_parts(context,root)
        else:
            bpy.ops.object.select_all(action='DESELECT');root.select_set(True);context.view_layer.objects.active=root
        return {'FINISHED'}

class NMSICON_OT_export(bpy.types.Operator,ExportHelper):
    bl_idname='nms_icon.export_json';bl_label='Export Icon JSON'
    filename_ext='.json';filter_glob:StringProperty(default='*.json',options={'HIDDEN'})
    @classmethod
    def poll(cls,context):return context.mode=='OBJECT' and selected(context) is not None
    def execute(self,context):
        try:
            payload=host().export_data(selected(context));Path(self.filepath).write_text(json.dumps(payload,indent=2),encoding='utf-8')
            self.report({'INFO'},f"Exported {len(payload['Objects'])} native parts")
            return {'FINISHED'}
        except Exception as exc:self.report({'ERROR'},str(exc));return {'CANCELLED'}

def draw(ui,context):
    s=context.scene.nms_icon_settings
    ui.label(text='SVG silhouette fitting - experimental',icon='INFO')
    ui.operator('nms_icon.import_svg',icon='FILE_FOLDER')
    if s.source:ui.label(text=s.source_name[:35],icon='FILE_IMAGE')
    ui.prop(s,'accuracy',slider=True);ui.prop(s,'max_parts')
    result=_cache.get(key(s)) if s.source else None
    if result is not None:
        name=preview_key(key(s))
        if _icons and name in _icons:
            ui.template_icon(icon_value=_icons[name].icon_id,scale=9)
        else:request_preview(context.scene)
        ui.label(text=f"{result['part_count']:,} panels / limit {s.max_parts:,}",icon='MESH_CUBE')
        ui.label(text=f"Outline: {result['outline_parts']} / Fill: {result['part_count']-result['outline_parts']}")
        ui.label(text=f"Sampled coverage: {result['coverage']:.1%}")
        ui.label(text='Amber = fitted; red = omitted detail')
    elif s.source and key(s) not in _errors and not bpy.app.timers.is_registered(refresh):
        # Drawing cannot write Scene properties; only queue a later refresh.
        request_preview(context.scene)
    if s.status:
        import textwrap
        for line in textwrap.wrap(s.status,38):ui.label(text=line)
    ui.prop(s,'panel_type');ui.prop(s,'height');ui.prop(s,'orientation');ui.prop(s,'face_offset');ui.prop(s,'palette')
    row=ui.row();row.enabled=bool(s.source) and bool(host().dependency_name())
    row.operator('nms_icon.generate',icon='ADD')
    root=selected(context)
    if root:
        box=ui.box();box.label(text=root.name,icon='OUTLINER_COLLECTION')
        box.operator('nms_icon.edit',text='Load Selected Icon Settings',icon='IMPORT')
        box.operator('nms_icon.replace',icon='FILE_REFRESH')
        row=box.row(align=True);row.operator('nms_icon.select',text='Select Parts').target='PARTS';row.operator('nms_icon.select',text='Select Control').target='CONTROL'
        box.operator('nms_icon.export_json',icon='EXPORT')
    ui.label(text='Single-colour silhouette; no image textures.')
    ui.label(text='Cursor = centre; bury rear geometry.')
    ui.label(text='Preview only: Update applies slider changes.')

def menu(self,context):
    if selected(context):self.layout.operator('nms_icon.edit',icon='IMAGE_DATA')

CLASSES=(NMSICON_Settings,NMSICON_OT_import,NMSICON_OT_generate,NMSICON_OT_load,NMSICON_OT_replace,NMSICON_OT_select,NMSICON_OT_export)
def register():
    global _icons
    _icons=bpy.utils.previews.new()
    for cls in CLASSES:bpy.utils.register_class(cls)
    bpy.types.Scene.nms_icon_settings=PointerProperty(type=NMSICON_Settings)
    bpy.types.VIEW3D_MT_object_context_menu.append(menu)
def unregister():
    global _icons
    if bpy.app.timers.is_registered(refresh):bpy.app.timers.unregister(refresh)
    _dirty.clear();_cache.clear();_errors.clear()
    bpy.types.VIEW3D_MT_object_context_menu.remove(menu)
    del bpy.types.Scene.nms_icon_settings
    for cls in reversed(CLASSES):bpy.utils.unregister_class(cls)
    if _icons is not None:bpy.utils.previews.remove(_icons);_icons=None
