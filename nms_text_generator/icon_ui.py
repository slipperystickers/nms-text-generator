"""Separate SVG mode and ownership. Text collections are never SVG targets."""
from .furby_errors import report_error
import hashlib
import importlib
import json
import math
import re
import time
import uuid
from pathlib import Path
import bpy
import bpy.utils.previews
from bpy.props import BoolProperty,StringProperty,IntProperty,FloatProperty,EnumProperty,PointerProperty,CollectionProperty,FloatVectorProperty
from bpy_extras.io_utils import ImportHelper,ExportHelper
from mathutils import Matrix
from . import icon_fit,panels,svg_geometry,color_match,curve_layout,preview_jobs

ROOT='nms_icon_root'
CONFIG='nms_icon_config'
_cache={}
_dirty={}
_errors=set()
_icons=None
_palette_icons=None
_palette_items=[]
_families=[]
_family_items={}
FAMILY_NAMES={'LEGACY':'Basic','FLAGS':'Flags','STONENATURAL':'Stone · natural','STONEROYAL':'Stone · royal',
              'STONEGREEN':'Stone · green','STONEBLUE':'Stone · blue','BUILDERS':'Salvaged',
              'BUILDERSB':'Salvaged · rusted','FIBREGLASS':'Alloy','FIBREGLASSB':'Alloy · rusted',
              'FIBREGLASSC':'Alloy · alternative','NEUTRAL':'Neutral','TIMBERBASIC':'Timber',
              'TIMBERROYAL':'Timber · royal','TIMBERSTAINED':'Timber · stained',
              'FREIGHTERBASE':'Freighter','BIGGS':'Corvette','STATION':'Station'}
_loading=False
_jobs=preview_jobs.Jobs()
_imports={}
_import_errors={}

def host():return importlib.import_module(__package__)
def selected(context):
    obj=context.active_object
    while obj is not None:
        if obj.get(ROOT):return obj
        obj=obj.parent
    return None

def key(settings):
    return (hashlib.sha256(settings.source.encode('utf-8')).hexdigest(),settings.accuracy,settings.max_parts,settings.match_colors,settings.include_station,color_match.overrides_json(settings.color_overrides))

def fitted(source,accuracy,max_parts,match_colors=False,include_station=False,color_overrides='{}'):
    color_overrides=color_match.overrides_json(color_overrides)
    k=(hashlib.sha256(source.encode('utf-8')).hexdigest(),accuracy,max_parts,match_colors,include_station,color_overrides)
    if k not in _cache:
        result=color_match.fit_svg(source,accuracy,max_parts,include_station,color_overrides) if match_colors else icon_fit.fit_svg(source,accuracy,max_parts)
        if len(_cache)>=6:_cache.pop(next(iter(_cache)))
        _cache[k]=result
    return _cache[k]

def preview_key(k):return 'SVG_'+hashlib.sha256(repr(k).encode()).hexdigest()

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
    for name,job in list(_jobs.active.items()):
        scene=bpy.data.scenes.get(name)
        pending=_imports.get(name)
        expected=pending[1] if pending else job.key
        if scene is None or not hasattr(scene,'nms_icon_settings') or key(scene.nms_icon_settings)!=expected:
            _jobs.cancel(name);_imports.pop(name,None);continue
        if not job.poll():continue
        s=scene.nms_icon_settings
        try:
            result=job.result()
            if pending and result.get('_rebuilt_source'):
                pending[0].update(source=result['_rebuilt_source'],original_source=pending[0]['source'],
                                  import_note='SVG rebuilt by tracing visible features. Small details may differ.')
            if len(_cache)>=6:_cache.pop(next(iter(_cache)))
            if pending:
                _import_errors.pop(name,None)
                _errors.discard(job.key)
                load(s,pending[0])
            _cache[key(s)]=result
            analyze(s)
        except preview_jobs.SimplificationNeeded as exc:
            if pending:
                _import_errors[name]=(pending[0],str(exc),True)
                bpy.ops.nms_icon.simplify_import('INVOKE_DEFAULT',source=pending[0]['source'],source_name=pending[0]['source_name'])
            else:s.status=str(exc);_errors.add(key(s))
        except Exception as exc:
            # A failed replacement belongs to its pending file, not the last
            # usable icon. Keep the previous preview and generation available.
            if pending:_import_errors[name]=(pending[0],str(exc),False)
            else:s.status=str(exc);_errors.add(key(s))
        finally:_jobs.cancel(name);_imports.pop(name,None)
    for name,when in list(_dirty.items()):
        if when>now or name in _imports:continue
        _dirty.pop(name,None);scene=bpy.data.scenes.get(name)
        if scene is None or not hasattr(scene,'nms_icon_settings'):continue
        s=scene.nms_icon_settings
        if not s.source:continue
        try:
            if key(s) in _cache:analyze(s)
            else:_jobs.start(name,key(s),{'kind':'icon','args':[s.source,s.accuracy,s.max_parts,s.match_colors,s.include_station,s.color_overrides]})
        except Exception as exc:s.status=str(exc);_errors.add(key(s))
    redraw()
    return .1 if _dirty or _jobs.active else None


def draw_busy(ui,job=None,text='Preparing preview'):
    elapsed=time.monotonic()-job.started if job else 0
    label=(job.stage if job else text)+f' · {int(elapsed)}s'
    # Indeterminate pulse: animation reports activity, not an invented percentage.
    ui.progress(factor=.15+.7*(.5+.5*math.sin(time.monotonic()*3)),type='BAR',text=label)


def ready(settings):
    return bpy.app.background or (settings.id_data.name not in _imports and key(settings) in _cache)


def analyze(settings):
    if not settings.source:raise ValueError('Import an SVG first.')
    k=key(settings)
    result=fitted(settings.source,settings.accuracy,settings.max_parts,settings.match_colors,settings.include_station,settings.color_overrides)
    # The preview is diagnostic, not an extra part in the generated collection.
    name=preview_key(k)
    if _icons is not None and name not in _icons:
        if len(_icons)>=6:
            for old in list(_icons.keys()):del _icons[old]
        icon=_icons.new(name);n=result['resolution'];icon.image_size=(n,n)
        icon.image_pixels_float=result['preview'][::-1].flatten()
    settings.preview_name=name
    if result['coverage']<.9:
        settings.status=f"Only {result['coverage']:.1%} of the artwork is filled. Raise the part limit; large areas are missing. Accuracy is a detail setting, not a coverage percentage."
    elif result['unfilled'] and result['budget_hit']:
        settings.status='Part limit: gaps/details remain. Raise the limit or reduce accuracy.'
    elif result['outline_relaxed']:
        settings.status='Outline simplified to fit the part budget. Raise the limit for finer curves.'
    elif result['outline_omissions']:
        settings.status='Ready. Very sharp tips are approximated.'
    else:settings.status='Ready. Outline first, then interior fill.'
    return result

FIELDS=('source','source_name','original_source','import_note','accuracy','max_parts','height','panel_type','orientation','face_offset','palette','match_colors','include_station','color_overrides','use_curve','curve_name','curve_fit')
def config(settings):return {field:getattr(settings,field) for field in FIELDS}
def load(settings,data):
    global _loading
    _loading=True
    try:
        # Old saved icons must retain their original single-colour behavior.
        data=dict(data);data.setdefault('match_colors',False);data.setdefault('include_station',False);data.setdefault('color_overrides','{}')
        data.setdefault('original_source','');data.setdefault('import_note','')
        for field,value in curve_layout.DEFAULTS.items():data.setdefault(field,value)
        data['color_overrides']=color_match.overrides_json(data['color_overrides'])
        for field in FIELDS:setattr(settings,field,data[field])
    finally:_loading=False
    if bpy.app.background:analyze(settings)
    else:request_preview(settings.id_data)

def create(context,data,matrix=None,user_data=None):
    a=host();b=a.get_builder(data['panel_type'])
    data=dict(data);data.setdefault('match_colors',False);data.setdefault('include_station',False);data.setdefault('color_overrides','{}')
    for field,value in curve_layout.DEFAULTS.items():data.setdefault(field,value)
    data['color_overrides']=color_match.overrides_json(data['color_overrides'])
    result=fitted(data['source'],data['accuracy'],data['max_parts'],data['match_colors'],data['include_station'],data['color_overrides'])
    if result['part_count']>data['max_parts']:raise ValueError('Fitted panel count exceeds the chosen limit.')
    path=curve_layout.Path(context,data) if data['use_curve'] else None
    overall=data['height']/result['bounds'][1];art_width=result['bounds'][0]*overall
    factor=path.fit(art_width,data['curve_fit']) if path else 1.
    matrix=(path.matrix if path else a.placement_matrix(context,data['orientation'])) if matrix is None else matrix.copy();a.check_matrix(matrix)
    user_data=(0 if data['match_colors'] else a.active_palette(context,data)) if user_data is None else user_data
    before={o.as_pointer() for o in bpy.data.objects};selection=list(context.selected_objects);active=context.view_layer.objects.active
    col=bpy.data.collections.new('NMS Icon - '+data['source_name'][:40]);context.scene.collection.children.link(col)
    uid=uuid.uuid4().hex;col[a.OWNER]=uid
    root=bpy.data.objects.new(col.name,None);col.objects.link(root)
    root[ROOT]=True;root[a.OWNER]=uid;root[CONFIG]=json.dumps(data)
    root['nms_text_userdata']=str(user_data);root['nms_text_part_count']=result['part_count']
    root['nms_icon_coverage']=result['coverage'];root.empty_display_size=data['height']*.12;root.matrix_world=matrix
    root['nms_icon_color_matches']=json.dumps(result.get('color_matches',[]))
    overall=data['height']/result['bounds'][1]
    try:
        bpy.ops.object.select_all(action='DESELECT');context.view_layer.objects.active=None
        for i,(x,y,width,angle) in enumerate(result['panels']):
            value=color_match.apply_userdata(user_data,result['panel_userdata'][i]) if data['match_colors'] else user_data
            part=b.add_part(data['panel_type'],user_data=value,build_rigs=False,high_res=True);obj=part.object
            # The stock builder's flat proxies do not display inverted/station
            # palettes reliably. Use an OBJECT material override for these new
            # generated proxies only; never alter a shared mesh or HD texture.
            if data['match_colors'] and not obj.data.get('nms_high_res_id') and not obj.get('nms_p'):
                match=next(m for m in result['color_matches'] if m['user_data']==result['panel_userdata'][i])
                name='NMScribe palette '+str(match['user_data'])
                material=bpy.data.materials.get(name)
                if material is None:
                    material=bpy.data.materials.new(name);material.diffuse_color=(*match['rgb'],1)
                if obj.material_slots:
                    obj.material_slots[0].link='OBJECT';obj.material_slots[0].material=material
            for old in list(obj.users_collection):old.objects.unlink(obj)
            col.objects.link(obj);obj.parent=root;obj.matrix_parent_inverse=Matrix.Identity(4)
            scale=width*overall/panels.FLAT_FOOTPRINT[1]
            rot=Matrix.Rotation(-angle,4,'Z')@Matrix.Rotation(math.pi/2,4,'X')
            # A tiny, bounded depth order prevents coincident textured panel
            # faces fighting where the fitter deliberately overlaps them.
            level=result['panel_depths'][i] if 'panel_depths' in result else i/max(1,result['part_count']-1)
            depth=level*data['height']*.002 if data['match_colors'] else 0
            pos=((x-result['bounds'][0]/2)*overall,(result['bounds'][1]/2-y)*overall,data['face_offset']+depth-panels.FLAT_FACE_Y*scale)
            native=Matrix.Translation(pos)@rot@Matrix.Scale(scale,4)
            if path:native=path.frame((pos[0]+art_width/2)*factor)@Matrix.Scale(factor,4)@Matrix.Translation((-pos[0],0,0))@native
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
    if curve_layout.STATE in root:data.update(curve_layout.DEFAULTS)
    user_data=a.active_palette(context,data) if not data.get('match_colors',False) and data['palette']=='ACTIVE' else int(root['nms_text_userdata'])
    staged=create(context,data,curve_layout.rebuild_matrix(root),user_data)
    curve_layout.reapply(context,root,staged)
    temp=staged.users_collection[0];dest=cols[0]
    for obj in a.managed_parts(staged):
        local=obj.matrix_basis.copy();obj.parent=root;obj.matrix_parent_inverse=Matrix.Identity(4);obj.matrix_basis=local
        obj[a.OWNER]=root[a.OWNER];dest.objects.link(obj);temp.objects.unlink(obj)
    for obj in parts:bpy.data.objects.remove(obj,do_unlink=True)
    for field in (CONFIG,'nms_text_userdata','nms_text_part_count','nms_icon_coverage','nms_icon_color_matches'):root[field]=staged[field]
    curve_layout.copy_state(staged,root)
    dest.name=staged.name;root.name=dest.name
    bpy.data.objects.remove(staged,do_unlink=True);bpy.data.collections.remove(temp)
    context.view_layer.update();a.select_parts(context,root);return root

class NMSICON_Settings(bpy.types.PropertyGroup):
    source: StringProperty(options={'HIDDEN'},update=changed)
    source_name: StringProperty(default='SVG icon')
    accuracy: IntProperty(name='Accuracy',default=50,min=0,max=100,subtype='PERCENTAGE',update=changed,description='Contour detail: lower values simplify curves into fewer facets; higher values retain finer contours. Part limit is a maximum. Preview only; press Generate or Update to apply')
    max_parts: IntProperty(name='Part limit',default=300,min=1,max=2000,update=changed,description='Hard upper limit; excess detail is omitted, never silently creates more parts')
    height: FloatProperty(name='Icon height',default=5,min=.05,max=10000,unit='LENGTH')
    panel_type: EnumProperty(name='Panel type',items=panels.ITEMS,default=panels.NEW_DEFAULT)
    orientation: EnumProperty(name='Orientation',items=[('FLAT','Flat (XY)','Front faces +Z'),('UPRIGHT','Upright (XZ)','Front faces -Y'),('CURSOR','3D Cursor rotation','Use cursor rotation')],default='FLAT')
    face_offset: FloatProperty(name='Face offset',default=.01,min=-1000,max=1000,unit='LENGTH')
    palette: EnumProperty(name='Colour / material',items=[('DEFAULT','Default / keep on update','Use default or keep original icon material'),('ACTIVE','Copy active part','Copy colour and material from active native part')],default='DEFAULT')
    match_colors: BoolProperty(name='Match SVG colours',default=False,update=changed,description='Keep visible solid-paint regions and choose the nearest NMS palette colour. Materials and lighting affect the final appearance')
    include_station: BoolProperty(name='Include station colours',default=False,update=changed,description='Also search station palette indices 115–150. Codes are from game data; appearance on these panel faces needs in-game validation')
    color_overrides: StringProperty(default='{}',options={'HIDDEN'},update=changed)
    use_curve: BoolProperty(name='Follow curve',default=False)
    curve_name: StringProperty(name='Curve',description='Blender curve used to bend this icon')
    curve_fit: BoolProperty(name='Fit to curve length',default=True,description='Uniformly scale the artwork to the curve length')
    status: StringProperty(options={'SKIP_SAVE'})
    preview_name: StringProperty(options={'SKIP_SAVE'})
    original_source: StringProperty(options={'HIDDEN'})
    import_note: StringProperty(options={'HIDDEN'})

def import_source(context,source,source_name,preflight=False,rebuild=False,strengthen=False):
    """Commit only after the accepted SVG has a valid fit; Cancel never calls this."""
    s=context.scene.nms_icon_settings
    data=config(s);data.update(source=source,source_name=source_name,color_overrides='{}',original_source='',import_note='')
    if bpy.app.background:
        result=preview_jobs.fit_icon([source,s.accuracy,s.max_parts,s.match_colors,s.include_station,'{}'],preflight,rebuild,strengthen)
        if result.get('_rebuilt_source'):
            data.update(source=result['_rebuilt_source'],original_source=source,import_note='SVG rebuilt by tracing visible features. Small details may differ.')
        k=(hashlib.sha256(data['source'].encode()).hexdigest(),s.accuracy,s.max_parts,s.match_colors,s.include_station,'{}')
        _cache[k]=result
        load(s,data);context.scene.nms_text_settings.mode='ICON'
        return result
    k=(hashlib.sha256(source.encode('utf-8')).hexdigest(),s.accuracy,s.max_parts,s.match_colors,s.include_station,'{}')
    name=context.scene.name
    _import_errors.pop(name,None)
    _jobs.cancel(name)
    _jobs.start(name,k,{'kind':'icon','preflight':preflight,'rebuild':rebuild,'strengthen':strengthen,'args':[source,s.accuracy,s.max_parts,s.match_colors,s.include_station,'{}']})
    _imports[name]=(data,key(s));_dirty.pop(name,None)
    context.scene.nms_text_settings.mode='ICON'
    if not bpy.app.timers.is_registered(refresh):bpy.app.timers.register(refresh,first_interval=.1)
    return {'outline_recovered':False}



class NMSICON_OT_simplify_import(bpy.types.Operator):
    bl_idname='nms_icon.simplify_import';bl_label='Simplify & Import';bl_options={'UNDO','INTERNAL'}
    bl_description='Trace the SVG outline with fewer line segments, then import it. The original file is unchanged'
    source:StringProperty(options={'HIDDEN','SKIP_SAVE'})
    source_name:StringProperty(options={'HIDDEN','SKIP_SAVE'})

    def invoke(self,context,event):
        return context.window_manager.invoke_props_dialog(self,width=430,title='Simplify SVG?',confirm_text='Simplify & Import',cancel_default=True)

    def draw(self,context):
        ui=self.layout
        ui.label(text='This SVG has dense or overlapping paths.',icon='INFO')
        ui.label(text='Combine strokes and rebuild a simpler outline?')
        ui.separator()
        ui.label(text='Very small details may change.')
        ui.label(text='Your original SVG file will not be changed.')

    def execute(self,context):
        try:
            import_source(context,self.source,self.source_name)
            self.report({'INFO'},'SVG simplified and imported. Preview it, then generate panels.')
            return {'FINISHED'}
        except Exception as exc:report_error(self,{'ERROR'},str(exc));return {'CANCELLED'}


class NMSICON_OT_import(bpy.types.Operator,ImportHelper):
    bl_idname='nms_icon.import_svg';bl_label='Import SVG';bl_options={'UNDO'}
    filename_ext='.svg'
    filter_glob:StringProperty(default='*.svg',options={'HIDDEN'})
    # Explicit opt-in for scripts/background tests; the normal UI asks first.
    simplify:BoolProperty(default=False,options={'HIDDEN','SKIP_SAVE'})
    def execute(self,context):
        try:
            path=Path(self.filepath)
            if path.stat().st_size>svg_geometry.MAX_BYTES:raise ValueError('SVG is larger than 1 MB. Simplify it first.')
            source=path.read_text(encoding='utf-8-sig')
            result=import_source(context,source,path.stem,preflight=not self.simplify)
            self.report({'INFO'},'SVG simplified and imported.' if result['outline_recovered'] else 'SVG loaded. Adjust accuracy, then generate native panels.')
            return {'FINISHED'}
        except icon_fit.SimplificationRequired as exc:
            self.report({'WARNING'},str(exc));return {'CANCELLED'}
        except Exception as exc:report_error(self,{'ERROR'},str(exc));return {'CANCELLED'}

class NMSICON_OT_rebuild_import(bpy.types.Operator):
    bl_idname='nms_icon.rebuild_import';bl_label='Rebuild & Import';bl_options={'UNDO','INTERNAL'}
    bl_description='Trace visible outlines and cutouts into a fresh SVG, preserving the original. Review the preview before generating'
    source:StringProperty(options={'HIDDEN','SKIP_SAVE'})
    source_name:StringProperty(options={'HIDDEN','SKIP_SAVE'})
    strengthen:BoolProperty(name='Strengthen thin lines',default=False,
                           description='Slightly thicken traced lines; this changes the artwork and narrows small gaps')
    def invoke(self,context,event):
        return context.window_manager.invoke_props_dialog(self,width=450,title='Rebuild SVG features?',confirm_text='Rebuild & Import',cancel_default=True)
    def draw(self,context):
        ui=self.layout
        ui.label(text='Trace visible outlines and cutouts into a new SVG.')
        ui.label(text='Small details may change. Review the preview.')
        ui.label(text='The original SVG is preserved.')
        if not context.scene.nms_icon_settings.match_colors:ui.prop(self,'strengthen')
    def execute(self,context):
        try:
            import_source(context,self.source,self.source_name,rebuild=True,
                          strengthen=self.strengthen and not context.scene.nms_icon_settings.match_colors)
            self.report({'INFO'},'Rebuilding SVG features. Review the preview before generating.')
            return {'FINISHED'}
        except Exception as exc:report_error(self,{'ERROR'},str(exc));return {'CANCELLED'}

class NMSICON_OT_generate(bpy.types.Operator):
    bl_idname='nms_icon.generate';bl_label='Generate New Icon';bl_options={'REGISTER','UNDO'}
    @classmethod
    def poll(cls,context):return context.mode=='OBJECT' and bool(context.scene.nms_icon_settings.source) and ready(context.scene.nms_icon_settings)
    def execute(self,context):
        try:
            root=create(context,dict(config(context.scene.nms_icon_settings),**curve_layout.DEFAULTS))
            coverage=root['nms_icon_coverage']
            self.report({'WARNING'} if coverage<.9 else {'INFO'},f"Created {root['nms_text_part_count']} native panels; {coverage:.1%} filled"+('. Raise the part limit for missing areas.' if coverage<.9 else ''))
            return {'FINISHED'}
        except Exception as exc:report_error(self,{'ERROR'},str(exc));return {'CANCELLED'}

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
        except Exception as exc:report_error(self,{'ERROR'},str(exc));return {'CANCELLED'}

class NMSICON_OT_replace(bpy.types.Operator):
    bl_idname='nms_icon.replace';bl_label='Update Selected Icon';bl_options={'REGISTER','UNDO'}
    bl_description='Replace only this icon’s generated panels, keeping its control and placement. Manual panel edits are replaced; Ctrl-Z undoes it'
    @classmethod
    def poll(cls,context):return context.mode=='OBJECT' and selected(context) is not None and bool(context.scene.nms_icon_settings.source) and ready(context.scene.nms_icon_settings)
    def execute(self,context):
        try:
            root=replace(context,selected(context),config(context.scene.nms_icon_settings))
            self.report({'INFO'},f"Updated icon: {root['nms_text_part_count']} panels")
            return {'FINISHED'}
        except Exception as exc:report_error(self,{'ERROR'},str(exc));return {'CANCELLED'}

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
        except Exception as exc:report_error(self,{'ERROR'},str(exc));return {'CANCELLED'}

def family_items(self,context):return _families
def palette_items(self,context):return _family_items.get(self.family,_palette_items[:1])
def family_changed(self,context):
    items=palette_items(self,context)
    if items:self.palette=items[0][0]

def station_changed(self,context):
    for row in self.rows:
        row.auto_code=color_match.nearest(color_match.parse_color(row.source_key)[0],self.include_station)['user_data']


class NMSICON_ColorChoice(bpy.types.PropertyGroup):
    source_key:StringProperty()
    source_color:FloatVectorProperty(size=3,subtype='COLOR',min=0,max=1)
    auto_code:IntProperty()
    family:EnumProperty(name='Palette',items=family_items,update=family_changed)
    palette:EnumProperty(name='NMS colour',items=palette_items)


class NMSICON_UL_colors(bpy.types.UIList):
    def draw_item(self,context,layout,data,item,icon,active_data,active_propname,index):
        split=layout.split(factor=.28)
        source=split.row(align=True);chip=source.row();chip.enabled=False
        chip.prop(item,'source_color',text='');source.label(text=item.source_key)
        choices=split.row(align=True);choices.prop(item,'family',text='')
        if item.family=='AUTO':
            target=_palette_items[item.auto_code+1]
            choices.label(text=target[1],icon_value=target[3])
        else:choices.prop(item,'palette',text='')


class NMSICON_OT_colors(bpy.types.Operator):
    bl_idname='nms_icon.colors';bl_label='SVG Colours';bl_options={'UNDO'}
    bl_description='Choose the NMS palette and colour for each SVG colour; Automatic uses the closest match'
    rows:CollectionProperty(type=NMSICON_ColorChoice)
    active_row:IntProperty(default=0)
    include_station:BoolProperty(name='Include station colours in automatic matching',default=False,update=station_changed)
    source_hash:StringProperty(options={'HIDDEN'})

    @classmethod
    def poll(cls,context):return bool(context.scene.nms_icon_settings.source) and context.scene.nms_icon_settings.match_colors

    def prepare(self,settings):
        self.rows.clear();self.include_station=settings.include_station
        self.source_hash=hashlib.sha256(settings.source.encode()).hexdigest()
        values=json.loads(settings.color_overrides)
        matches=color_match.read_paints(settings.source,settings.include_station)[2]
        paints={color_match.color_key(m['source_rgb']):m for m in matches}
        for paint,match in paints.items():
            row=self.rows.add();row.source_key=paint;row.source_color=color_match.linear(match['source_rgb'])
            row.auto_code=match['user_data'];row.family='AUTO'
            if paint in values:
                p=color_match.catalog()['palettes'][values[paint]]
                row.family=re.sub(r'\d+$','',p['id']);row.palette=str(p['index'])

    def invoke(self,context,event):
        try:self.prepare(context.scene.nms_icon_settings)
        except Exception as exc:report_error(self,{'ERROR'},str(exc));return {'CANCELLED'}
        return context.window_manager.invoke_props_dialog(self,width=650,title='SVG Colours',confirm_text='Apply Colours')

    def draw(self,context):
        ui=self.layout;ui.label(text='SVG colour                         NMS palette / colour')
        ui.template_list('NMSICON_UL_colors','',self,'rows',self,'active_row',rows=min(8,max(3,len(self.rows))))
        ui.prop(self,'include_station')

    def execute(self,context):
        s=context.scene.nms_icon_settings
        try:
            if self.source_hash!=hashlib.sha256(s.source.encode()).hexdigest():raise ValueError('The SVG changed. Open SVG Colours again.')
            values={row.source_key:int(row.palette) for row in self.rows if row.family!='AUTO'}
            data=config(s);data.update(color_overrides=color_match.overrides_json(values),include_station=self.include_station)
            # Stage the fit before committing, so a failed choice leaves settings intact.
            if bpy.app.background:fitted(s.source,s.accuracy,s.max_parts,s.match_colors,self.include_station,data['color_overrides'])
            load(s,data);redraw();return {'FINISHED'}
        except Exception as exc:report_error(self,{'ERROR'},str(exc));return {'CANCELLED'}


class NMSICON_OT_options(bpy.types.Operator):
    bl_idname='nms_icon.options';bl_label='Icon Options'
    def invoke(self,context,event):return context.window_manager.invoke_popup(self,width=360)
    def draw(self,context):
        s=context.scene.nms_icon_settings;ui=self.layout
        ui.prop(s,'panel_type');ui.prop(s,'orientation');ui.prop(s,'face_offset')
        if not s.match_colors:ui.prop(s,'palette')
    def execute(self,context):return {'FINISHED'}


class NMSICON_OT_details(bpy.types.Operator):
    bl_idname='nms_icon.details';bl_label='Fit Details'
    def invoke(self,context,event):return context.window_manager.invoke_popup(self,width=420)
    def draw(self,context):
        s=context.scene.nms_icon_settings;result=_cache.get(key(s));ui=self.layout
        if result:
            ui.label(text=f"{result['part_count']:,} panels / limit {s.max_parts:,}")
            if result.get('faceted_fit'):
                ui.label(text='Faceted outline: panels stay inside the contour')
                ui.label(text=f"Contour segments: {sum(map(len,result['_fill_loops']))}")
                ui.label(text=f"Fitted silhouette covered: {result['face_coverage']:.1%}")
                ui.label(text=f"Shape change: {result['shape_change']:.1%} of SVG area")
                ui.label(text='Native interior seams: none detected' if result['seam_check_complete'] else 'Native joins need more parts')
                if result.get('simplification_limited'):ui.label(text='Further simplification would damage cutouts')
            else:
                ui.label(text=f"Outline: {result['outline_parts']} / Fill: {result['part_count']-result['outline_parts']}")
                ui.label(text=f"Sampled coverage: {result['coverage']:.1%}")
            ui.label(text='Preview: estimated palette colours; red = omitted detail' if s.match_colors else 'Preview: amber = fitted; red = omitted detail')
            if result.get('outline_recovered'):ui.label(text='SVG outline simplified for import')
        if s.status:
            import textwrap
            for line in textwrap.wrap(s.status,54):ui.label(text=line)
        if s.import_note:
            import textwrap
            for line in textwrap.wrap(s.import_note,54):ui.label(text=line)
        failure=_import_errors.get(context.scene.name)
        if failure:
            import textwrap
            ui.separator();ui.label(text='Import: '+failure[0]['source_name'])
            for line in textwrap.wrap(failure[1],54):ui.label(text=line)
        ui.separator();ui.label(text='Generate creates panels at the 3D cursor.')
        ui.label(text='Update Selected Icon applies preview changes.')
    def execute(self,context):return {'FINISHED'}

def draw(ui,context):
    s=context.scene.nms_icon_settings
    ui.operator('nms_icon.import_svg',icon='FILE_FOLDER')
    row=ui.row();row.scale_y=1.8
    row.operator('nms_icon.generate',text='GENERATE ICON',icon='ADD',depress=True)
    root=selected(context)
    if root:ui.operator('nms_icon.replace',icon='FILE_REFRESH')
    curve_layout.draw(ui,context)
    if s.source:ui.label(text=s.source_name[:35],icon='FILE_IMAGE')
    if s.import_note:ui.label(text='Rebuilt SVG · review preview',icon='INFO')
    result=_cache.get(key(s)) if s.source else None
    job=_jobs.active.get(context.scene.name)
    if context.scene.name in _imports:draw_busy(ui,job)
    elif s.source and result is None and key(s) not in _errors:draw_busy(ui,job)
    if result is not None:
        name=preview_key(key(s))
        if _icons and name in _icons:
            ui.template_icon(icon_value=_icons[name].icon_id,scale=6)
        else:request_preview(context.scene)
        label=f"{result['part_count']:,} panels"
        if result['coverage']<.95:label+=f" · {result['coverage']:.0%} filled"
        elif s.match_colors:label+=f" · {result.get('color_count',0)} colours"
        row=ui.row(align=True);row.alert=result['coverage']<.9;row.label(text=label,icon='ERROR' if result['coverage']<.9 else 'MESH_CUBE')
        row.operator('nms_icon.details',text='',icon='INFO')
    elif s.source and key(s) not in _errors and not bpy.app.timers.is_registered(refresh):
        # Drawing cannot write Scene properties; only queue a later refresh.
        request_preview(context.scene)
    if key(s) in _errors:
        box=ui.box();box.label(text='SVG needs attention',icon='ERROR')
        import textwrap
        for line in textwrap.wrap(s.status or 'Open Fit Details for the error.',34):box.label(text=line)
        box.operator('nms_icon.details',icon='INFO')
    failure=_import_errors.get(context.scene.name)
    if failure:
        data,message,can_simplify=failure
        box=ui.box();box.label(text='SVG can be simplified' if can_simplify else 'SVG import failed',icon='INFO' if can_simplify else 'ERROR')
        box.label(text=data['source_name'][:35])
        import textwrap
        for line in textwrap.wrap(message,34):box.label(text=line)
        if can_simplify:
            op=box.operator('nms_icon.simplify_import',icon='MOD_SIMPLIFY');op.source=data['source'];op.source_name=data['source_name']
        else:
            op=box.operator('nms_icon.rebuild_import',icon='FILE_REFRESH');op.source=data['source'];op.source_name=data['source_name']
        box.operator('nms_icon.details',icon='INFO')
    elif s.source:
        op=ui.operator('nms_icon.rebuild_import',text='Rebuild SVG Features',icon='FILE_REFRESH')
        op.source=s.original_source or s.source;op.source_name=s.source_name
    ui.prop(s,'accuracy',slider=True);ui.prop(s,'max_parts');ui.prop(s,'height')
    row=ui.row(align=True);row.prop(s,'match_colors',text='Match colours');row.operator('nms_icon.colors',text='Colours',icon='COLOR')
    ui.operator('nms_icon.options',icon='PREFERENCES')
    if root:
        box=ui.box();box.label(text=root.name,icon='OUTLINER_COLLECTION')
        box.operator('nms_icon.edit',text='Load Selected Icon Settings',icon='IMPORT')
        row=box.row(align=True);row.operator('nms_icon.select',text='Select Parts').target='PARTS';row.operator('nms_icon.select',text='Select Control').target='CONTROL'
        box.operator('nms_icon.export_json',icon='EXPORT')

def menu(self,context):
    if selected(context):self.layout.operator('nms_icon.edit',icon='IMAGE_DATA')

CLASSES=(NMSICON_Settings,NMSICON_ColorChoice,NMSICON_UL_colors,NMSICON_OT_colors,NMSICON_OT_options,NMSICON_OT_details,NMSICON_OT_simplify_import,NMSICON_OT_rebuild_import,NMSICON_OT_import,NMSICON_OT_generate,NMSICON_OT_load,NMSICON_OT_replace,NMSICON_OT_select,NMSICON_OT_export)
def register():
    global _icons,_palette_icons
    _icons=bpy.utils.previews.new()
    _palette_icons=bpy.utils.previews.new()
    _palette_items.clear();_families.clear();_family_items.clear()
    _palette_items.append(('AUTO','Automatic','Choose the closest available NMS colour',0,0))
    _families.append(('AUTO','Automatic','Closest colour match',0,0))
    for p in color_match.catalog()['palettes']:
        family=re.sub(r'\d+$','',p['id'])
        if family not in _family_items:
            _families.append((family,FAMILY_NAMES.get(family,family.title()),'Choose a colour from this NMS palette',0,len(_families)))
            _family_items[family]=[]
        icon=_palette_icons.new(str(p['index']));icon.image_size=(32,32)
        icon.image_pixels_float=[*color_match.srgb(p['p']),1]*1024
        label=p['name_key'].removeprefix('UI_PALETTE_').replace('_',' ').title() if p['name_key'].startswith('UI_PALETTE_') else 'Colour '+str(p['index'])
        entry=(str(p['index']),label,f"{FAMILY_NAMES.get(family,family.title())}: {p['id']} (code {p['index']})",icon.icon_id,p['index']+1)
        _palette_items.append(entry);_family_items[family].append(entry)
    for cls in CLASSES:bpy.utils.register_class(cls)
    bpy.types.Scene.nms_icon_settings=PointerProperty(type=NMSICON_Settings)
    bpy.types.VIEW3D_MT_object_context_menu.append(menu)
def unregister():
    global _icons,_palette_icons
    if bpy.app.timers.is_registered(refresh):bpy.app.timers.unregister(refresh)
    _jobs.close();_imports.clear();_import_errors.clear()
    _dirty.clear();_cache.clear();_errors.clear()
    icon_fit.read_outline.cache_clear()
    icon_fit.read_source.cache_clear()
    color_match.read_regions.cache_clear();color_match.read_paints.cache_clear()
    bpy.types.VIEW3D_MT_object_context_menu.remove(menu)
    del bpy.types.Scene.nms_icon_settings
    for cls in reversed(CLASSES):bpy.utils.unregister_class(cls)
    if _icons is not None:bpy.utils.previews.remove(_icons);_icons=None
    if _palette_icons is not None:bpy.utils.previews.remove(_palette_icons);_palette_icons=None
    _palette_items.clear();_families.clear();_family_items.clear()
