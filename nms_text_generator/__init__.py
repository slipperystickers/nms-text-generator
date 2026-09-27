bl_info = {
    'name': 'NMScribe for Blender Base Builder',
    'author': 'FuriousFurby',
    'version': (2, 0, 1),
    'blender': (5, 1, 0),
    'location': '3D View > Sidebar > NMS Text',
    'description': 'Native-panel text and SVG icons through NMS Base Builder; separate NMS Text tab',
    'category': 'Object',
}

import json
import math
import textwrap
import uuid
from pathlib import Path

import bpy
import bpy.utils.previews
from bpy.app.handlers import persistent
from bpy.props import BoolProperty, EnumProperty, FloatProperty, IntProperty, PointerProperty, StringProperty
from bpy_extras.io_utils import ExportHelper
from mathutils import Matrix, Vector

from . import backend, layout, panels, text_input, icon_ui

OWNER = 'nms_text_owner'
ROOT = 'nms_text_root'
CONFIG = 'nms_text_config'
SEQUENCE = 'nms_text_sequence'
FIELDS = ('font', 'panel_type', 'text', 'text_version', 'height', 'letter_gap', 'word_gap', 'line_gap', 'alignment', 'orientation', 'face_offset', 'palette')
LEGACY_DEFAULTS = {'font': 'FUTURE_Z', 'panel_type': panels.DEFAULT}
_previews = None
_font_items = []
_settings_lock = False
_pending_font = None
_active_inputs = []

def auto_switch_toggled(settings,context):
    settings.auto_font_initialized=True

def initialize_auto_switch():
    for scene in bpy.data.scenes:
        settings=scene.nms_text_settings
        if not settings.is_property_set('text_version'):
            settings.text=layout.decode_legacy(settings.text)
            settings.text_version=2
        settings.text=layout.field_text(settings.text)
        if not settings.auto_font_initialized:
            settings.auto_font=True
            settings.auto_font_initialized=True
    return None

@persistent
def initialize_auto_switch_on_load(_):
    initialize_auto_switch()

def upgrade_config(config):
    config=dict(config)
    if config.get('text_version',1)<2:
        config['text']=layout.decode_legacy(config['text'])
    config['text_version']=2
    return config


def load_settings(settings,config):
    global _settings_lock
    _settings_lock=True
    try:
        config=upgrade_config(config)
        config['text']=layout.field_text(config['text'])
        for key in FIELDS:
            setattr(settings,key,config.get(key,LEGACY_DEFAULTS.get(key)) if key in LEGACY_DEFAULTS else config[key])
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
    queue_style_change(settings,context,'font')


def panel_changed(settings,context):
    queue_style_change(settings,context,'panel_type')


def queue_style_change(settings,context,field):
    global _pending_font
    if _settings_lock or not settings.auto_font or context is None:return
    root=fully_selected_root(context)
    if root is None:return
    config=json.loads(root[CONFIG])
    current=(config.get('font','FUTURE_Z'),config.get('panel_type',panels.DEFAULT))
    identity=(root.name,root.get(OWNER),root[CONFIG])
    desired=list(_pending_font[3:5] if _pending_font and _pending_font[:3]==identity else current)
    desired[0 if field=='font' else 1]=getattr(settings,field)
    if current==tuple(desired):
        _pending_font=None
        return
    # Only apply the control actually changed, not stale settings from another
    # sign. Coalesce rapid font + part changes while retaining the saved text.
    _pending_font=identity+tuple(desired)+(settings.font,settings.panel_type)
    # Defer object mutations out of the RNA update callback. An operator gives
    # the rebuild its own undo step and runs on Blender's main thread.
    if not bpy.app.timers.is_registered(apply_pending_font):
        bpy.app.timers.register(apply_pending_font,first_interval=.05)

def apply_pending_font():
    global _pending_font
    pending=_pending_font
    _pending_font=None
    if not pending or not hasattr(bpy.context.scene,'nms_text_settings'):return None
    name,owner,original,font,panel_type,observed_font,observed_panel=pending
    root=fully_selected_root(bpy.context)
    settings=bpy.context.scene.nms_text_settings
    if (root is None or root.name!=name or root.get(OWNER)!=owner or
            root[CONFIG]!=original or settings.font!=observed_font or settings.panel_type!=observed_panel or not settings.auto_font):return None
    try:
        bpy.ops.nms_text.change_font('EXEC_DEFAULT',font=font,panel_type=panel_type)
    except Exception as exc:
        settings.edit_status='Font / panel change failed: '+str(exc)
    return None

def font_items(self,context):
    # Keep strings/tuples alive: Blender's dynamic enum callback retains references.
    return _font_items

def load_banner():
    """Run after registration: Blender restricts bpy.data during addon enable."""
    if _previews is None or 'BANNER' in _previews:return None
    brand=Path(__file__).parent/'previews'/'nmscribe_sidebar.png'
    try:
        _load_banner_tiles(brand)
    except Exception as exc:
        # Decorative branding must never prevent the text tool from loading.
        if 'BANNER' in _previews:del _previews['BANNER']
        print('NMScribe: banner unavailable:',exc)
    for window in bpy.context.window_manager.windows:
        for area in window.screen.areas:
            if area.type=='VIEW_3D':area.tag_redraw()
    return None


def _load_banner_tiles(brand):
    if brand.exists():
        # Preserve one continuous banner; never split lettering across icons.
        import numpy as np
        source=bpy.data.images.load(str(brand),check_existing=False)
        try:
            # Preview pixels are display-encoded, unlike ordinary linear image
            # pixels. Do not feed scene-linear RGB into a UI icon.
            source.colorspace_settings.name='Non-Color'
            width,height=source.size
            data=np.empty(width*height*4,dtype=np.float32)
            source.pixels.foreach_get(data)
            data=data.reshape(height,width,4)
            # Blender UI previews blend premultiplied RGBA. PNG pixels are
            # straight-alpha; unassociated RGB otherwise produces bright fringes.
            data[:,:,:3]*=data[:,:,3:4]
            # Offline Lanczos filtering avoids aliasing when the UI draws this
            # near 200px. The high-resolution approved master is kept separately.
            icon=_previews.new('BANNER')
            icon.image_size=(width,height)
            icon.image_pixels_float=data.flatten()
        finally:bpy.data.images.remove(source)


def load_previews():
    global _previews
    # A prior failed enable may have allocated previews without registering UI.
    if _previews is not None:bpy.utils.previews.remove(_previews)
    _previews=bpy.utils.previews.new()
    brand=Path(__file__).parent/'previews'/'nmscribe.png'
    if brand.exists():_previews.load('NMSCRIBE',str(brand),'IMAGE')
    _font_items.clear()
    for index,(key,name,path) in enumerate(layout.FONTS):
        icon=0
        preview=Path(__file__).parent/'previews'/(key.lower()+'.png')
        if preview.exists():
            icon=_previews.load(key,str(preview),'IMAGE').icon_id
        _font_items.append((key,name,name+' — native panels, A-Z, 0-9 and symbols',icon,index))

def dependency_name():
    return backend.dependency_name(bpy.context.preferences.addons.keys())

def get_builder(part_id=panels.DEFAULT):
    b = backend.resolve(bpy.context.preferences.addons.keys())
    index = b.get_asset_index()
    missing = {panels.validate(part_id)} - set(index)
    if missing:
        raise ValueError('Base Builder is missing required native panel assets: ' + ', '.join(sorted(missing)))
    return b

def config_from_settings(settings):
    return {key:getattr(settings,key) for key in FIELDS}

def make_plan(config):
    config=upgrade_config(config)
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
    config = upgrade_config(config)
    config.setdefault('panel_type',panels.DEFAULT)
    part_id = panels.validate(config['panel_type'])
    b = get_builder(part_id)
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
                part = b.add_part(part_id,user_data=user_data,build_rigs=False,high_res=True)
                obj = part.object
                for old_collection in list(obj.users_collection):
                    old_collection.objects.unlink(obj)
                collection.objects.link(obj)
                obj.parent = root
                obj.matrix_parent_inverse = Matrix.Identity(4)
                native_matrix = b.Part.create_matrix_from_vectors(record['Position'],record['Up'],record['At'])
                obj.matrix_basis = offset @ scale @ panels.from_flat_matrix(native_matrix,part_id)
                obj[OWNER] = uid
                obj[SEQUENCE] = sequence
                obj['nms_text_character'] = placement['char']
                obj['nms_text_glyph_index'] = glyph_index
                obj['nms_text_line'] = placement['line']
                obj.select_set(False)
                context.view_layer.objects.active = None
                if obj.get('ObjectID') != part_id or not obj.material_slots:
                    raise ValueError('Base Builder did not return the expected native panel and materials.')
                if getattr(b,'requires_high_res',True) and not obj.data.name.startswith('NMS_HR_'):
                    raise ValueError('The HD provider did not return the expected high-resolution native panel.')
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
        if obj.get('ObjectID') not in ('BUILDFLATPANEL','STORAGEPANEL','CUBEWALL'):
            raise ValueError('A managed part has an unexpected native item ID.')
        records.append(b.Part.deserialise_from_object(obj,b.BUILDER).serialise())
    return {'BaseVersion':5,'Objects':records}

class NMSTEXT_Settings(bpy.types.PropertyGroup):
    mode: EnumProperty(name='Mode',items=[('TEXT','Text','Existing panel lettering'),('ICON','Icon / Sticker','Fit native panels to an SVG silhouette')],default='TEXT')
    font: EnumProperty(name='Font',items=font_items,default=0,update=font_changed,description='Choose a font; auto-switch rebuilds a fully selected sign')
    panel_type: EnumProperty(name='Panel type',items=panels.ITEMS,default=panels.NEW_DEFAULT,update=panel_changed,description='Native item used for each piece; Storage uses its plain back. Same layout and count')
    auto_font: BoolProperty(name='Auto-switch selected text',default=True,update=auto_switch_toggled,description='Changing Font or Panel type rebuilds one fully selected sign. Manual panel edits are replaced; Ctrl-Z undoes it')
    auto_font_initialized: BoolProperty(default=False,options={'HIDDEN'})
    edit_status: StringProperty(options={'SKIP_SAVE'})
    text: StringProperty(name='Text',default='CCB',description='Use <br> for a new line. Backslashes are literal. No other HTML is interpreted')
    text_version: IntProperty(default=2,options={'HIDDEN'})
    height: FloatProperty(name='Letter height',default=5,min=.05,max=10000,unit='LENGTH')
    letter_gap: FloatProperty(name='Letter gap',default=1,min=0,max=10000,unit='LENGTH')
    word_gap: FloatProperty(name='Space width',default=3,min=.05,max=10000,unit='LENGTH')
    line_gap: FloatProperty(name='Line gap',default=1.5,min=0,max=10000,unit='LENGTH')
    face_offset: FloatProperty(name='Face offset',default=.01,min=-1000,max=1000,unit='LENGTH',description='Distance in front of the 3D Cursor plane; rear geometry is intended to be buried')
    alignment: EnumProperty(name='Alignment',items=[('LEFT','Left','Baseline starts at the cursor'),('CENTER','Center','Each line centered on the cursor'),('RIGHT','Right','Each line ends at the cursor')],default='LEFT')
    orientation: EnumProperty(name='Orientation',items=[('FLAT','Flat (XY)','Front faces +Z'),('UPRIGHT','Upright (XZ)','Front faces -Y'),('CURSOR','3D Cursor rotation','Use the full rotation of the 3D Cursor')],default='FLAT')
    palette: EnumProperty(name='Colour / material',items=[('DEFAULT','Default / keep on replace','Native default for new text; preserve current palette when replacing'),('ACTIVE','Copy active NMS part','Copy the selected part\'s UserData palette and material finish')],default='DEFAULT')

class NMSTEXT_OT_input(bpy.types.Operator):
    """Focused, cancel-safe text entry; owns no global keyboard shortcuts."""
    bl_idname='nms_text.input'
    bl_label='NMS Text - Edit Text'
    bl_description='Edit text: Shift+Enter inserts a line, Enter confirms, Escape cancels'
    edit_config: StringProperty(options={'HIDDEN','SKIP_SAVE'})
    root_name: StringProperty(options={'HIDDEN','SKIP_SAVE'})
    owner: StringProperty(options={'HIDDEN','SKIP_SAVE'})

    @classmethod
    def poll(cls,context):
        return context.area is not None and context.area.type=='VIEW_3D' and not _active_inputs

    def invoke(self,context,event):
        self._area=context.area
        self._region=next((r for r in self._area.regions if r.type=='WINDOW'),None)
        if self._region is None:return {'CANCELLED'}
        self._config=upgrade_config(json.loads(self.edit_config)) if self.edit_config else None
        self._buffer=text_input.Buffer(self._config['text'] if self._config else context.scene.nms_text_settings.text,layout.MAX_INPUT)
        self._scene=context.scene;self._scroll=0;self._follow=True;self._message=''
        self._handle=bpy.types.SpaceView3D.draw_handler_add(self.draw_input,(context,), 'WINDOW','POST_PIXEL')
        _active_inputs.append(self)
        context.window_manager.modal_handler_add(self)
        self._area.tag_redraw()
        return {'RUNNING_MODAL'}

    def cleanup(self):
        if getattr(self,'_handle',None) is not None:
            bpy.types.SpaceView3D.draw_handler_remove(self._handle,'WINDOW');self._handle=None
        if self in _active_inputs:_active_inputs.remove(self)
        try:self._area.tag_redraw()
        except ReferenceError:pass

    def cancel(self,context):self.cleanup()

    def finish(self,context,accept):
        if accept:
            try:layout.normalize(self._buffer.text)
            except ValueError as exc:
                self._message=str(exc);return {'RUNNING_MODAL'}
        self.cleanup()
        if not accept:return {'CANCELLED'}
        if self._config is None:
            self._scene.nms_text_settings.text=self._buffer.text
            self._scene.nms_text_settings.text_version=2
        else:
            self._config['text']=self._buffer.text
            self._config['text_version']=2
            # Stage text first, then use the existing cancel-safe layout dialog.
            bpy.ops.nms_text.edit('INVOKE_DEFAULT',dialog_only=True,
                                 root_name=self.root_name,owner=self.owner,**self._config)
        return {'FINISHED'}

    def geometry(self):
        # Sidebars can overlay WINDOW rather than reducing its width.
        left,right=0,self._region.width
        for region in self._area.regions:
            if region.type=='UI' and region.width>1 and self._area.spaces.active.show_region_ui:
                edge=region.x-self._region.x
                if 0<edge<right:right=edge
            if region.type=='TOOLS' and region.width>1 and self._area.spaces.active.show_region_toolbar:
                edge=region.x+region.width-self._region.x
                if 0<edge<right:left=max(left,edge)
        width=max(180,min(720,right-left-32))
        height=max(150,min(380,self._region.height-32))
        x=left+(right-left-width)/2;y=(self._region.height-height)/2
        return x,y,width,height

    def draw_input(self,context):
        if bpy.context.area!=self._area:return
        import blf,gpu
        from gpu_extras.batch import batch_for_shader
        x,y,w,h=self.geometry()
        colors=context.preferences.themes[0].user_interface.wcol_text
        bg=tuple(colors.inner);fg=tuple(colors.text)+(1.,)
        shader=gpu.shader.from_builtin('UNIFORM_COLOR')
        def rect(x0,y0,width,height,color):
            batch=batch_for_shader(shader,'TRIS',{'pos':[(x0,y0),(x0+width,y0),(x0+width,y0+height),(x0,y0),(x0+width,y0+height),(x0,y0+height)]})
            shader.bind();shader.uniform_float('color',color);batch.draw(shader)
        def label(text,px,py,size=14,color=fg):
            blf.size(0,size);blf.color(0,*color);blf.position(0,px,py,0);blf.draw(0,text)
        gpu.state.blend_set('ALPHA')
        try:
            rect(x-2,y-2,w+4,h+4,(.4,.4,.4,1))
            rect(x,y,w,h,(bg[0],bg[1],bg[2],1))
            label('NMS Text - Edit Text',x+16,y+h-27,17)
            label('Shift+Enter: new line   Enter: done   Esc: cancel',x+16,y+h-48,12)
            self._columns=max(10,int((w-32)/10));self._visible=max(1,int((h-116)/21))
            rows=self._buffer.rows(self._columns)
            caret=max(i for i,(start,line) in enumerate(rows) if start<=self._buffer.cursor)
            if self._follow:
                self._scroll=max(0,min(self._scroll,caret))
                if caret>=self._scroll+self._visible:self._scroll=caret-self._visible+1
            self._scroll=min(self._scroll,max(0,len(rows)-self._visible));self._follow=False
            a,b=sorted((self._buffer.cursor,self._buffer.anchor))
            self._grid=(x+16,y+h-78)
            for row,(start,line) in enumerate(rows[self._scroll:self._scroll+self._visible]):
                py=self._grid[1]-row*21
                for col,char in enumerate(line):
                    px=self._grid[0]+col*10
                    if a<=start+col<b:rect(px,py-3,10,20,(.22,.36,.6,.7))
                    label(char,px,py)
                if row+self._scroll==caret:
                    rect(self._grid[0]+(self._buffer.cursor-start)*10,py-3,1.5,19,fg)
            label(self._message[:max(10,int((w-32)/7))] if self._message else f'{len(self._buffer.text)} / {layout.MAX_INPUT} characters',x+16,y+47,12)
            self._done=(x+w-196,y+12,84,26);self._cancel=(x+w-102,y+12,86,26)
            for bounds,text in ((self._done,'Done'),(self._cancel,'Cancel')):
                rect(*bounds,(.24,.27,.34,1));label(text,bounds[0]+14,bounds[1]+6,13,(1,1,1,1))
        finally:gpu.state.blend_set('NONE')

    def modal(self,context,event):
        if self._handle is None:return {'CANCELLED'}
        if self._area.type!='VIEW_3D':
            self.cleanup();return {'CANCELLED'}
        self._area.tag_redraw()
        if event.type in ('ESC','RIGHTMOUSE') and event.value=='PRESS':return self.finish(context,False)
        if event.type in ('WHEELUPMOUSE','WHEELDOWNMOUSE'):
            self._scroll=max(0,self._scroll+(-3 if event.type=='WHEELUPMOUSE' else 3));self._follow=False
            return {'RUNNING_MODAL'}
        if event.type=='LEFTMOUSE' and event.value=='PRESS' and hasattr(self,'_grid'):
            px=event.mouse_x-self._region.x;py=event.mouse_y-self._region.y
            def inside(box):return box[0]<=px<=box[0]+box[2] and box[1]<=py<=box[1]+box[3]
            if inside(self._done):return self.finish(context,True)
            if inside(self._cancel):return self.finish(context,False)
            rows=self._buffer.rows(self._columns)
            row=int((self._grid[1]+17-py)//21)+self._scroll
            if 0<=row<len(rows) and self._grid[0]<=px<self._grid[0]+self._columns*10:
                start,line=rows[row]
                self._buffer.move(start+min(len(line),max(0,round((px-self._grid[0])/10))),event.shift)
            return {'RUNNING_MODAL'}
        if event.value!='PRESS':return {'RUNNING_MODAL'}
        self._message='';self._follow=True
        ctrl=event.ctrl or event.oskey
        if ctrl and event.type in ('C','X','V'):
            if event.type in ('C','X'):
                context.window_manager.clipboard=self._buffer.selected()
                if event.type=='X' and self._buffer.selected():self._buffer.replace('')
            elif not self._buffer.replace(context.window_manager.clipboard):self._message='Text exceeds the 2,000-character limit.'
        elif event.type in ('RET','NUMPAD_ENTER') and not event.shift:return self.finish(context,True)
        elif self._buffer.key(event.type,event.shift,ctrl):pass
        elif event.unicode and not ctrl and not event.alt:
            if not self._buffer.replace(event.unicode):self._message='Text exceeds the 2,000-character limit.'
        return {'RUNNING_MODAL'}


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
    panel_type: EnumProperty(items=(('KEEP','Keep panel type','Preserve the current native item'),)+panels.ITEMS,default='KEEP')
    @classmethod
    def poll(cls,context):return fully_selected_root(context) is not None
    def execute(self,context):
        root=fully_selected_root(context)
        if root is None:return {'CANCELLED'}
        config=json.loads(root[CONFIG])
        config['font']=self.font
        config['panel_type']=config.get('panel_type',panels.DEFAULT) if self.panel_type=='KEEP' else self.panel_type
        config['palette']='DEFAULT'
        try:
            replace_text(context,root,config)
            load_settings(context.scene.nms_text_settings,config)
            context.scene.nms_text_settings.edit_status='Font / panel type updated. Ctrl-Z to undo.'
            return {'FINISHED'}
        except Exception as exc:
            load_settings(context.scene.nms_text_settings,json.loads(root[CONFIG]))
            context.scene.nms_text_settings.edit_status='Font / panel change failed: '+str(exc)
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
    dialog_only: BoolProperty(default=False,options={'HIDDEN','SKIP_SAVE'})
    @classmethod
    def poll(cls,context):return context.mode=='OBJECT' and selected_root(context) is not None
    def invoke(self,context,event):
        root=selected_root(context)
        if root is None:
            self.report({'ERROR'},'Select a panel belonging to generated NMS text first.')
            return {'CANCELLED'}
        self.root_name=root.name
        self.owner=root.get(OWNER)
        config=config_from_settings(self) if getattr(self,'dialog_only',False) else upgrade_config(json.loads(root[CONFIG]))
        config.setdefault('font','FUTURE_Z')
        config.setdefault('panel_type',panels.DEFAULT)
        config['palette']='DEFAULT'
        config['text']=layout.field_text(config['text'])
        for key in FIELDS:setattr(self,key,config[key])
        return context.window_manager.invoke_props_dialog(self,width=420)
    def draw(self,context):
        ui=self.layout
        ui.prop(self,'text')
        ui.label(text='<br> = new line')
        ui.prop(self,'font')
        ui.prop(self,'panel_type')
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
    bl_label='NMScribe'
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
        brand=ui.box()
        if _previews and 'BANNER' in _previews:
            banner=brand.row(align=True)
            banner.alignment='CENTER'
            banner.ui_units_y=2.7
            banner.template_icon(icon_value=_previews['BANNER'].icon_id,scale=10)
        else:brand.label(text='NMScribe')
        donation=brand.column(align=True)
        donation.enabled=False
        donation.scale_y=.8
        donation.label(text='Donated to the Community by')
        donation.label(text='Corvette Class Builders (CCB)')
        brand.operator('wm.url_open',text='CCB / Traveller Toolkit',icon='URL').url='https://discord.gg/arbW3DvM5y'
        ui.prop(settings,'mode',expand=True)
        ui.label(text='Native panel lettering - v2.0.1')
        if settings.mode=='ICON':
            icon_ui.draw(ui,context)
            return
        ui.prop(settings,'auto_font')
        ui.prop(settings,'font')
        ui.prop(settings,'panel_type')
        ui.template_icon_view(settings,'font',show_labels=True,scale=6.0,scale_popup=7.0)
        if settings.auto_font and fully_selected_root(context):
            ui.label(text='Font / panel changes rebuild this sign.',icon='INFO')
        if settings.edit_status:
            for line in textwrap.wrap(settings.edit_status,42):ui.label(text=line)
        ui.prop(settings,'text')
        ui.label(text='<br> = new line')
        ui.label(text='A-Z, 0-9 and symbols',icon='INFO')
        ui.label(text='- _ / \\ ? ! | [ ] + = : .')
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
    icon_ui.register()
    bpy.types.VIEW3D_MT_object_context_menu.append(text_context_menu)
    bpy.app.handlers.load_post.append(initialize_auto_switch_on_load)
    bpy.app.timers.register(initialize_auto_switch,first_interval=0)
    bpy.app.timers.register(load_banner,first_interval=.1)

def unregister():
    global _previews,_pending_font
    icon_ui.unregister()
    for editor in list(_active_inputs):editor.cleanup()
    _pending_font=None
    if initialize_auto_switch_on_load in bpy.app.handlers.load_post:
        bpy.app.handlers.load_post.remove(initialize_auto_switch_on_load)
    if bpy.app.timers.is_registered(initialize_auto_switch):bpy.app.timers.unregister(initialize_auto_switch)
    if bpy.app.timers.is_registered(load_banner):bpy.app.timers.unregister(load_banner)
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
