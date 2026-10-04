"""Sample Blender curves without modifying them; place rigid native parts."""
from bisect import bisect_right
import importlib
import json
import math
import bpy
from bpy.props import BoolProperty,EnumProperty,FloatProperty
from mathutils import Matrix,Vector

DEFAULTS={'use_curve':False,'curve_name':'','curve_fit':True}
STATE='nms_curve_layout'
TARGET='nms_curve_target'


def draw(ui,context):
    ui.operator('nms_text.follow_curve',text='Follow Curve',icon='CURVE_PATH')
    settings=context.scene.nms_curve_settings
    row=ui.row()
    row.prop(settings,'expanded',text='Curve Options',icon='TRIA_DOWN' if settings.expanded else 'TRIA_RIGHT',emboss=False)
    if settings.expanded:
        box=ui.box()
        box.label(text='Select artwork + one curve.')
        box.prop(settings,'fit',text='Fit to curve length')
        box.prop(settings,'reverse',text='Reverse direction')
        box.prop(settings,'phase',text='Around curve')
        box.prop(settings,'orientation',text='Facing')
        box.operator('nms_text.restore_flat',text='Restore Flat Layout',icon='LOOP_BACK')


class NMSCURVE_Settings(bpy.types.PropertyGroup):
    expanded:BoolProperty(default=False,options={'SKIP_SAVE'})
    fit:BoolProperty(name='Fit to curve length',default=True,description='Uniformly scale the complete artwork to the selected curve')
    reverse:BoolProperty(name='Reverse direction',default=False,description='Read along the curve in the opposite direction')
    phase:FloatProperty(name='Around curve',subtype='ANGLE',default=0,min=-2*math.pi,max=2*math.pi,description='Move the artwork around a closed curve by this angle, then click Follow Curve. 90 degrees moves one quarter of the way around')
    orientation:EnumProperty(name='Facing',items=[('AUTO','Match artwork','Use the artwork\'s saved orientation'),('FLAT','Flat','Follow the curve in its local XY plane'),('UPRIGHT','Upright','Stand along the curve with local Z up')],default='AUTO')


def host():return importlib.import_module(__package__)


def selection(context,require_curve=True):
    """Resolve selected parts or controls independently of the active object."""
    roots={};curves=[]
    for selected in context.selected_objects:
        if selected.type=='CURVE':curves.append(selected);continue
        obj=selected
        while obj is not None:
            if obj.get('nms_text_root') or obj.get('nms_icon_root'):
                roots[obj.as_pointer()]=obj;break
            obj=obj.parent
    if len(roots)!=1:raise ValueError('Select one generated text/icon and one Blender curve. A panel or its control selects the whole artwork.')
    if require_curve and len(curves)!=1:raise ValueError('Select exactly one Blender curve together with the generated text/icon.')
    return next(iter(roots.values())),curves[0] if len(curves)==1 else None


def config_key(root):return 'nms_icon_config' if root.get('nms_icon_root') else 'nms_text_config'
def rows(matrix):return [list(row) for row in matrix]


def local_matrices(root,parts):
    inverse=root.matrix_world.inverted()
    return {str(p['nms_text_sequence']):inverse@p.matrix_world for p in parts}


def legacy_flat(context,root,parts,matrices,config):
    """Invert the old generator's known placement, retaining local part edits."""
    a=host();path=Path(context,config)
    if root.get('nms_icon_root'):
        result=a.icon_ui.fitted(config['source'],config['accuracy'],config['max_parts'],config.get('match_colors',False),config.get('include_station',False),config.get('color_overrides','{}'))
        if result['part_count']!=root.get('nms_text_part_count') or abs(result['coverage']-root.get('nms_icon_coverage',-1))>1e-6:
            raise ValueError('This older curved icon uses a different fit. Generate a new flat icon before following a curve.')
        overall=config['height']/result['bounds'][1];width=result['bounds'][0]*overall
        factor=path.fit(width,config['curve_fit'])
        for part in parts:
            key=str(part[a.SEQUENCE]);x=result['panels'][part[a.SEQUENCE]][0]*overall-width/2
            bend=path.frame((x+width/2)*factor)@Matrix.Scale(factor,4)@Matrix.Translation((-x,0,0))
            matrices[key]=bend.inverted()@matrices[key]
    else:
        plan=a.make_plan(config);font=a.layout.library(config.get('font','FUTURE_Z'))
        width=max(plan['line_widths']);factor=path.fit(width,config['curve_fit'])
        anchor={'LEFT':0,'CENTER':width/2,'RIGHT':width}[config['alignment']]
        for part in parts:
            placement=plan['placements'][part['nms_text_glyph_index']]
            glyph_width=font['widths'][placement['char']]*plan['scale']
            distance=(placement['x']+glyph_width/2+anchor)*factor
            offset=path.frame(distance)@Matrix.Scale(factor,4)@Matrix.Translation((-glyph_width/2,placement['y'],config['face_offset']))
            flat=Matrix.Translation((placement['x'],placement['y'],config['face_offset']))
            key=str(part[a.SEQUENCE]);matrices[key]=flat@offset.inverted()@matrices[key]
    return matrices


def flat_layout(context,root,parts):
    a=host();config=json.loads(root[config_key(root)])
    current=local_matrices(root,parts)
    if len(current)!=len(parts):raise ValueError('The artwork contains duplicate panel identifiers. Generate a new group first.')
    state=json.loads(root[STATE]) if STATE in root else None
    if state:
        if set(current)!=set(state['rest']):raise ValueError('Panels were added or removed after following the curve. Undo that change before restoring or following again.')
        # Carry local edits made since the previous application back to flat
        # space, then reapply once. Repeated clicks never compound the bend.
        rest={key:Matrix(state['rest'][key])@Matrix(state['applied'][key]).inverted()@matrix for key,matrix in current.items()}
        return Matrix(state['root'])@Matrix.Scale(root.matrix_world.to_scale().x,4),rest,config
    if config.get('use_curve'):current=legacy_flat(context,root,parts,current,config)
    return root.matrix_world.copy(),current,config


def face_points(part,matrix):
    a=host();pid=part['ObjectID'];a.panels.validate(pid)
    flat=matrix@a.panels.from_flat_matrix(Matrix.Identity(4),pid).inverted()
    half_long=a.panels.FLAT_FOOTPRINT[0]/2;half_short=a.panels.FLAT_FOOTPRINT[1]/2
    return [flat@Vector((x,a.panels.FLAT_FACE_Y,z)) for x in (-half_long,half_long) for z in (-half_short,half_short)]


def write_layout(context,root,parts,matrix,locals):
    extras={obj:obj.matrix_world.copy() for obj in root.children if obj not in parts}
    root.matrix_world=matrix
    for part in parts:
        part.matrix_basis=part.matrix_parent_inverse.inverted()@locals[str(part['nms_text_sequence'])]
    context.view_layer.update()
    for obj,world in extras.items():obj.matrix_world=world
    context.view_layer.update()


def follow(context,root,curve,fit=True,reverse=False,orientation='AUTO',phase=0):
    a=host();parts=a.managed_parts(root)
    if not parts:raise ValueError('The selected artwork has no generated panels.')
    a.check_matrix(root.matrix_world)
    for part in parts:a.check_matrix(part.matrix_world)
    original,rest,config=flat_layout(context,root,parts)
    facing=config['orientation'] if orientation=='AUTO' else orientation
    path=Path(context,dict(config,curve_name=curve.name,orientation=facing))
    if abs(phase)>1e-7 and not path.closed:
        raise ValueError('Around curve needs a closed curve, such as a Bezier Circle. Set the angle to 0 for an open curve.')
    scale=original.to_scale().x
    scaled={key:Matrix.Scale(scale,4)@matrix for key,matrix in rest.items()}
    extents={str(p[a.SEQUENCE]):face_points(p,scaled[str(p[a.SEQUENCE])]) for p in parts}
    low=min(v.x for vs in extents.values() for v in vs);high=max(v.x for vs in extents.values() for v in vs)
    factor=path.fit(high-low,fit)
    groups={}
    for part in parts:
        key=str(part[a.SEQUENCE]);group=('glyph',int(part['nms_text_glyph_index'])) if root.get(a.ROOT) and 'nms_text_glyph_index' in part else ('part',key)
        groups.setdefault(group,[]).append(key)
    staged={}
    for keys in groups.values():
        points=[v for key in keys for v in extents[key]]
        x=(min(v.x for v in points)+max(v.x for v in points))/2
        distance=(x-low)*factor
        position=path.length-distance if reverse else distance
        if path.closed:position=(position+phase/(2*math.pi)*path.length)%path.length
        frame=path.frame(position)
        if reverse:frame=frame@Matrix.Rotation(math.pi,4,'Y')
        transform=frame@Matrix.Scale(factor,4)@Matrix.Translation((-x,0,0))
        for key in keys:staged[key]=transform@scaled[key]
    for matrix in staged.values():a.check_matrix(path.matrix@matrix)
    snapshot={'version':1,'root':rows(original),'rest':{key:rows(m) for key,m in rest.items()},'applied':{key:rows(m) for key,m in staged.items()},'fit':fit,'reverse':reverse,'orientation':orientation,'phase':phase,'curve_name':curve.name}
    # All evaluation and validation precede the first change to artwork.
    previous_root=root.matrix_world.copy();previous=local_matrices(root,parts)
    previous_config=root[config_key(root)];previous_state=root.get(STATE);previous_target=root.get(TARGET)
    try:
        write_layout(context,root,parts,path.matrix,staged)
        root[STATE]=json.dumps(snapshot);root[TARGET]=curve
        config.update(DEFAULTS);root[config_key(root)]=json.dumps(config)
    except Exception:
        write_layout(context,root,parts,previous_root,previous)
        root[config_key(root)]=previous_config
        if previous_state is not None:root[STATE]=previous_state
        elif STATE in root:del root[STATE]
        if previous_target is not None:root[TARGET]=previous_target
        elif TARGET in root:del root[TARGET]
        raise
    return len(parts)


def restore(context,root):
    a=host();parts=a.managed_parts(root)
    matrix,rest,config=flat_layout(context,root,parts)
    for local in rest.values():a.check_matrix(matrix@local)
    write_layout(context,root,parts,matrix,rest)
    config.update(DEFAULTS);root[config_key(root)]=json.dumps(config)
    for key in (STATE,TARGET):
        if key in root:del root[key]


def rebuild_matrix(root):
    return Matrix(json.loads(root[STATE])['root']) if STATE in root else root.matrix_world


def reapply(context,root,staged):
    if STATE not in root:return
    try:
        state=json.loads(root[STATE]);curve=root.get(TARGET)
        if curve is None:raise ValueError('The followed curve is missing. Restore Flat Layout or select a replacement curve and click Follow Curve.')
        follow(context,staged,curve,state['fit'],state['reverse'],state['orientation'],state.get('phase',0))
    except Exception:
        # The normal rebuild has not committed yet. Remove only its new group.
        a=host();collections=list(staged.users_collection)
        for part in a.managed_parts(staged):bpy.data.objects.remove(part,do_unlink=True)
        bpy.data.objects.remove(staged,do_unlink=True)
        for collection in collections:
            if not collection.objects:bpy.data.collections.remove(collection)
        a.select_parts(context,root)
        raise


def copy_state(staged,root):
    if STATE in staged:
        parts=host().managed_parts(root);extras={obj:obj.matrix_world.copy() for obj in root.children if obj not in parts}
        root[STATE]=staged[STATE];root[TARGET]=staged[TARGET];root.matrix_world=staged.matrix_world.copy()
        bpy.context.view_layer.update()
        for obj,world in extras.items():obj.matrix_world=world


class NMSTEXT_OT_follow_curve(bpy.types.Operator):
    bl_idname='nms_text.follow_curve';bl_label='Follow Curve';bl_options={'REGISTER','UNDO'}
    bl_description='Select generated text/icon panels (or their control) and one curve, then click to move the whole artwork along it. Either selection may be active'
    @classmethod
    def poll(cls,context):
        if context.mode!='OBJECT':return False
        try:selection(context);return True
        except ValueError as exc:cls.poll_message_set(str(exc));return False
    def execute(self,context):
        try:
            root,curve=selection(context);s=context.scene.nms_curve_settings
            count=follow(context,root,curve,s.fit,s.reverse,s.orientation,s.phase)
            settings=context.scene.nms_icon_settings if root.get('nms_icon_root') else context.scene.nms_text_settings
            for field,value in DEFAULTS.items():setattr(settings,field,value)
            self.report({'INFO'},f'{count} existing panels now follow {curve.name}. Ctrl-Z to undo.')
            return {'FINISHED'}
        except Exception as exc:self.report({'ERROR'},str(exc));return {'CANCELLED'}


class NMSTEXT_OT_restore_flat(bpy.types.Operator):
    bl_idname='nms_text.restore_flat';bl_label='Restore Flat Layout';bl_options={'REGISTER','UNDO'}
    bl_description='Return selected artwork to its flat layout and original placement; retain local panel edits and colours'
    @classmethod
    def poll(cls,context):
        if context.mode!='OBJECT':return False
        try:
            root,_=selection(context,False)
            return STATE in root or json.loads(root[config_key(root)]).get('use_curve',False)
        except (ValueError,KeyError):return False
    def execute(self,context):
        try:restore(context,selection(context,False)[0]);return {'FINISHED'}
        except Exception as exc:self.report({'ERROR'},str(exc));return {'CANCELLED'}


class Path:
    def __init__(self,context,config):
        obj=bpy.data.objects.get(config.get('curve_name',''))
        if obj is None or obj.type!='CURVE':raise ValueError('Choose a Blender curve in Follow curve first.')
        if len(obj.data.splines)!=1:raise ValueError('Use a curve with one continuous spline.')
        context.view_layer.update()
        evaluated=obj.evaluated_get(context.evaluated_depsgraph_get())
        if len(evaluated.data.splines)!=1:raise ValueError('Use a curve with one continuous spline.')
        # Blender samples Bezier, Poly and rational NURBS through its own curve
        # evaluator. A temporary copy removes surface/bevel settings only.
        data=evaluated.data.copy();copy=bpy.data.objects.new('NMScribe curve sampling',data)
        mesh=None
        try:
            data.dimensions='3D';data.bevel_depth=0;data.extrude=0;data.offset=0
            data.bevel_object=None;data.taper_object=None;data.resolution_u=max(64,data.resolution_u)
            context.scene.collection.objects.link(copy);context.view_layer.update()
            mesh=copy.to_mesh()
            if mesh is None or not mesh.edges:raise ValueError('The curve has no usable length.')
            adjacent={i:[] for i in range(len(mesh.vertices))}
            for edge in mesh.edges:
                a,b=edge.vertices;adjacent[a].append(b);adjacent[b].append(a)
            if any(len(v)>2 or not v for v in adjacent.values()):raise ValueError('Use one continuous, unbranched curve.')
            ends=[i for i,v in adjacent.items() if len(v)==1]
            start=ends[0] if ends else 0;order=[start];visited={start};previous=None;current=start
            while True:
                nexts=[i for i in adjacent[current] if i!=previous]
                if not nexts:break
                nxt=nexts[0]
                if nxt==start:order.append(start);break
                if nxt in visited:raise ValueError('The curve contains a disconnected section.')
                order.append(nxt);visited.add(nxt);previous,current=current,nxt
            if len(visited)!=len(mesh.vertices):raise ValueError('Use one continuous curve.')
            self.matrix=Matrix.Translation(obj.matrix_world.translation)@obj.matrix_world.to_quaternion().to_matrix().to_4x4()
            transform=self.matrix.inverted()@obj.matrix_world
            points=[transform@mesh.vertices[i].co for i in order]
        finally:
            if mesh is not None:copy.to_mesh_clear()
            bpy.data.objects.remove(copy,do_unlink=True);bpy.data.curves.remove(data)
        self.closed=not ends
        self.points=[points[0]]
        for point in points[1:]:
            if (point-self.points[-1]).length>1e-7:self.points.append(point)
        if len(self.points)<2:raise ValueError('The curve has no usable length.')
        self.distances=[0.]
        for a,b in zip(self.points,self.points[1:]):self.distances.append(self.distances[-1]+(b-a).length)
        self.length=self.distances[-1];self.rotations=[]
        up=Vector((0,0,1) if config['orientation']=='UPRIGHT' else (0,1,0))
        if config['orientation']=='CURSOR':up=self.matrix.to_3x3().inverted()@(context.scene.cursor.matrix.to_3x3()@Vector((0,1,0)))
        normal_hint=Vector((0,0,1))
        if config['orientation']=='CURSOR':normal_hint=self.matrix.to_3x3().inverted()@(context.scene.cursor.matrix.to_3x3()@Vector((0,0,1)))
        last=None
        for i,point in enumerate(self.points):
            if self.closed and i in (0,len(self.points)-1):
                tangent=(self.points[1]-self.points[-2]).normalized()
            else:
                tangent=(self.points[min(i+1,len(self.points)-1)]-self.points[max(0,i-1)]).normalized()
            if tangent.length<.5:raise ValueError('The curve reverses sharply. Smooth its cusp before generating.')
            # Flat artwork follows the path's plane even when the first
            # tangent is parallel to Y (as on Blender's default circle).
            if last is None and config['orientation']!='UPRIGHT':up=normal_hint.cross(tangent)
            if last is not None:up=last.rotation_difference(tangent)@up
            up=up-tangent*up.dot(tangent)
            if up.length<1e-6:
                reference=Vector((0,0,1)) if abs(tangent.z)<.9 else Vector((0,1,0))
                up=reference-tangent*reference.dot(tangent)
            up.normalize();normal=tangent.cross(up).normalized()
            self.rotations.append(Matrix((tangent,up,normal)).transposed().to_quaternion().normalized());last=tangent

    def frame(self,distance):
        if distance < -1e-5 or distance > self.length+1e-5:
            raise ValueError('Artwork is longer than the curve. Enable Fit to curve length or use a longer curve.')
        distance=max(0,min(self.length,distance));i=min(len(self.points)-2,max(0,bisect_right(self.distances,distance)-1))
        t=(distance-self.distances[i])/(self.distances[i+1]-self.distances[i])
        # Near-identical samples can use an approximate slerp. Normalize its
        # result so conversion to a matrix cannot introduce scale/shear.
        rotation=self.rotations[i].slerp(self.rotations[i+1],t).normalized()
        return Matrix.Translation(self.points[i].lerp(self.points[i+1],t))@rotation.to_matrix().to_4x4()

    def fit(self,width,enabled):
        if width<=1e-7:raise ValueError('Artwork has no usable width.')
        if not enabled and width>self.length+1e-5:
            raise ValueError('Artwork is longer than the curve. Enable Fit to curve length or use a longer curve.')
        return self.length/width if enabled else 1.


class NMSTEXT_OT_pick_curve(bpy.types.Operator):
    bl_idname='nms_text.pick_curve';bl_label='Use Selected Curve';bl_options={'UNDO'}
    bl_description='Use the active Blender curve as the path'
    @classmethod
    def poll(cls,context):return context.active_object is not None and context.active_object.type=='CURVE'
    def execute(self,context):
        s=context.scene.nms_icon_settings if context.scene.nms_text_settings.mode=='ICON' else context.scene.nms_text_settings
        s.curve_name=context.active_object.name;s.use_curve=True;return {'FINISHED'}
