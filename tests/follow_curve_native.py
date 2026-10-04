"""Selection-driven curve placement on real native parts; isolated Blender."""
import json,os,sys,math
from pathlib import Path
from unittest.mock import patch
import bpy,addon_utils
from mathutils import Matrix

ROOT=Path(__file__).resolve().parents[1]
if '--installed' not in sys.argv:sys.path.insert(0,str(ROOT))
sys.path.insert(0,str(ROOT/'tests'))
from native_bootstrap import enable_dependencies
provider=enable_dependencies()
if '--forge' in sys.argv:
    sys.path.insert(0,os.environ['NMS_COLOR_TEST_FORGE_PATH'])
    addon_utils.enable(os.environ['NMS_COLOR_TEST_FORGE'],default_set=True)
import nms_text_generator as a
from nms_text_generator import curve_layout as c,icon_ui as icons
a.register();ctx=bpy.context
fresh=bpy.data.scenes.new('Fresh default verification')
assert not fresh.nms_icon_settings.match_colors
bpy.data.scenes.remove(fresh)
assert not ctx.scene.nms_curve_settings.expanded


def close(x,y,eps=3e-4):
    assert max(abs(x[i][j]-y[i][j]) for i in range(4) for j in range(4))<eps


def select(root,curve=None,active_curve=True,partial=False):
    bpy.ops.object.select_all(action='DESELECT')
    target=a.managed_parts(root)[0] if partial else root
    target.select_set(True)
    if curve:curve.select_set(True)
    ctx.view_layer.objects.active=curve if curve and active_curve else target


def new_curve(name,length=30):
    data=bpy.data.curves.new(name,'CURVE');data.dimensions='3D'
    spline=data.splines.new('BEZIER');spline.bezier_points.add(2)
    for point,co in zip(spline.bezier_points,((0,0,0),(length*.5,3,1),(length,0,2))):
        point.co=co;point.handle_left_type='AUTO';point.handle_right_type='AUTO'
    data.bevel_depth=.12
    obj=bpy.data.objects.new(name,data);ctx.scene.collection.objects.link(obj)
    obj.matrix_world=Matrix.Translation((7,-2,4))@Matrix.Rotation(.3,4,'Z')
    ctx.view_layer.update();return obj


curve=new_curve('Selected path');other_curve=new_curve('Other path')
roots=[]
for mode in ('text','icon'):
    for pid in ('BUILDFLATPANEL','STORAGEPANEL'):
        if mode=='text':
            cfg=dict(a.config_from_settings(ctx.scene.nms_text_settings),text='NMS',height=1,panel_type=pid,use_curve=False)
            root=a.create_text(ctx,cfg)
        else:
            cfg=dict(icons.config(ctx.scene.nms_icon_settings),source='<svg><rect width="80" height="20" fill="red"/><rect x="30" y="20" width="20" height="40" fill="blue"/></svg>',source_name='Curve button icon',accuracy=40,max_parts=60,height=2,panel_type=pid,match_colors=True,use_curve=False)
            root=icons.create(ctx,cfg)
        root.matrix_world=Matrix.Translation((2,4,6))@Matrix.Rotation(.2,4,'Z')@Matrix.Scale(1.3,4)
        parts=a.managed_parts(root)
        # Deliberate local edit and unique palette must survive the operation.
        parts[0].matrix_basis=parts[0].matrix_basis@Matrix.Scale(1.04,4)
        parts[0]['UserData']=str(150)
        extra=bpy.data.objects.new('Unmanaged child',None);ctx.scene.collection.objects.link(extra);extra.parent=root
        ctx.view_layer.update();extra_world=extra.matrix_world.copy()
        original={p.name:p.matrix_world.copy() for p in parts};ids={p.as_pointer() for p in parts}
        meshes={p.name:p.data for p in parts};materials={p.name:[slot.material for slot in p.material_slots] for p in parts}
        original_root=root.matrix_world.copy();before=set(bpy.data.objects)
        select(root,curve,active_curve=True,partial=True)
        assert bpy.ops.nms_text.follow_curve.poll()
        assert bpy.ops.nms_text.follow_curve()=={'FINISHED'}
        assert set(bpy.data.objects)==before and ids=={p.as_pointer() for p in a.managed_parts(root)}
        assert parts[0]['UserData']=='150'
        assert all(p.data==meshes[p.name] and [s.material for s in p.material_slots]==materials[p.name] for p in parts)
        close(extra.matrix_world,extra_world)
        assert ctx.active_object==curve and curve.select_get()
        for p in parts:a.check_matrix(p.matrix_world)
        assert len({tuple(round(v,3) for v in p.matrix_world.to_quaternion()) for p in parts})>1
        # Applying again is stable, regardless of which selected object is active.
        bent={p.name:p.matrix_world.copy() for p in parts}
        select(root,curve,active_curve=False)
        assert bpy.ops.nms_text.follow_curve()=={'FINISHED'}
        for p in parts:close(p.matrix_world,bent[p.name])
        select(root)
        assert bpy.ops.nms_text.restore_flat()=={'FINISHED'}
        close(root.matrix_world,original_root)
        for p in parts:close(p.matrix_world,original[p.name])
        # Reverse / keep-size options remain uniform and round-trip exactly.
        ctx.scene.nms_curve_settings.reverse=True;ctx.scene.nms_curve_settings.fit=False
        select(root,curve);assert bpy.ops.nms_text.follow_curve()=={'FINISHED'}
        for p in parts:assert abs(p.matrix_world.to_scale().x-original[p.name].to_scale().x)<3e-4
        select(root);assert bpy.ops.nms_text.restore_flat()=={'FINISHED'}
        for p in parts:close(p.matrix_world,original[p.name])
        ctx.scene.nms_curve_settings.reverse=False;ctx.scene.nms_curve_settings.fit=True
        # Invalid path and non-uniform artwork fail without changing any objects.
        curve.data.splines.new('POLY');before=set(bpy.data.objects)
        try:c.follow(ctx,root,curve);assert False
        except ValueError:pass
        assert set(bpy.data.objects)==before
        for p in parts:close(p.matrix_world,original[p.name])
        curve.data.splines.remove(curve.data.splines[-1])
        select(root,curve);other_curve.select_set(True);assert not bpy.ops.nms_text.follow_curve.poll()
        select(root);assert not bpy.ops.nms_text.follow_curve.poll()
        roots.append(root)

# A default Bezier circle used to create tiny non-uniform scales during
# quaternion interpolation, rejecting untouched text as stretched.
bpy.ops.curve.primitive_bezier_circle_add()
circle=ctx.object
cfg=dict(a.config_from_settings(ctx.scene.nms_text_settings),text='FuriousFurby',font='VECTOR',height=5,panel_type='STORAGEPANEL',use_curve=False)
circle_text=a.create_text(ctx,cfg)
for curve_scale in ((1,1,1),(.07,.07,.07),(12,8,5)):
    circle.scale=curve_scale;ctx.view_layer.update()
    path=c.Path(ctx,dict(cfg,curve_name=circle.name))
    assert path.closed
    for step in range(1001):a.check_matrix(path.frame(path.length*step/1000))
    close(path.frame(0),path.frame(path.length))
    for root in (circle_text,roots[-1]):
        parts=a.managed_parts(root);original={p.name:p.matrix_world.copy() for p in parts}
        before=set(bpy.data.objects)
        select(root,circle);assert bpy.ops.nms_text.follow_curve()=={'FINISHED'}
        assert set(bpy.data.objects)==before
        for p in parts:a.check_matrix(p.matrix_world)
        a.export_data(root)  # The native export scale guard must still pass.
        bent={p.name:p.matrix_world.copy() for p in parts}
        if curve_scale==(1,1,1):
            ctx.scene.nms_curve_settings.phase=math.pi/2
            assert bpy.ops.nms_text.follow_curve()=={'FINISHED'}
            quarter=Matrix.Rotation(-math.pi/2,4,'Z')
            for p in parts:close(p.matrix_world,quarter@bent[p.name],eps=.002)
            rotated={p.name:p.matrix_world.copy() for p in parts}
            assert bpy.ops.nms_text.follow_curve()=={'FINISHED'}
            for p in parts:close(p.matrix_world,rotated[p.name])
            assert abs(json.loads(root[c.STATE])['phase']-math.pi/2)<1e-6
            ctx.scene.nms_curve_settings.phase=2*math.pi
            assert bpy.ops.nms_text.follow_curve()=={'FINISHED'}
            for p in parts:close(p.matrix_world,bent[p.name])
            ctx.scene.nms_curve_settings.phase=-math.pi/2
            assert bpy.ops.nms_text.follow_curve()=={'FINISHED'}
            for p in parts:close(p.matrix_world,quarter.inverted()@bent[p.name],eps=.002)
            ctx.scene.nms_curve_settings.phase=0
        select(root,circle,active_curve=False);assert bpy.ops.nms_text.follow_curve()=={'FINISHED'}
        for p in parts:close(p.matrix_world,bent[p.name])
        select(root);assert bpy.ops.nms_text.restore_flat()=={'FINISHED'}
        for p in parts:close(p.matrix_world,original[p.name])
# Real non-uniform artwork must still be refused without changing parts.
circle_text.scale=(1,1.1,1);ctx.view_layer.update()
snapshot={p.name:p.matrix_world.copy() for p in a.managed_parts(circle_text)}
try:c.follow(ctx,circle_text,circle);assert False
except ValueError as exc:assert 'stretched' in str(exc)
for p in a.managed_parts(circle_text):close(p.matrix_world,snapshot[p.name])
circle_text.scale=(1,1,1);ctx.view_layer.update()
snapshot={p.name:p.matrix_world.copy() for p in a.managed_parts(circle_text)}
try:c.follow(ctx,circle_text,curve,phase=math.pi/2);assert False
except ValueError as exc:assert 'closed curve' in str(exc)
for p in a.managed_parts(circle_text):close(p.matrix_world,snapshot[p.name])

# The previous recipe-based curve API still loads, and can be converted safely.
cfg=dict(a.config_from_settings(ctx.scene.nms_text_settings),text='OLD',height=1,use_curve=True,curve_name=curve.name,curve_fit=True)
legacy=a.create_text(ctx,cfg)
select(legacy,curve);assert bpy.ops.nms_text.follow_curve()=={'FINISHED'}
select(legacy);assert bpy.ops.nms_text.restore_flat()=={'FINISHED'}
assert not json.loads(legacy[a.CONFIG])['use_curve']
# Rebuild text on the remembered curve, including a changed glyph count.
select(roots[0],curve);bpy.ops.nms_text.follow_curve()
cfg=dict(json.loads(roots[0][a.CONFIG]),text='NEW TEXT')
a.replace_text(ctx,roots[0],cfg)
assert c.STATE in roots[0] and roots[0][c.TARGET]==curve
select(roots[0]);assert bpy.ops.nms_text.restore_flat()=={'FINISHED'}

# Stored target is an object reference and survives renaming and save/reopen.
root=roots[-1];curve=circle
ctx.scene.nms_curve_settings.phase=math.pi/2
select(root,curve);bpy.ops.nms_text.follow_curve()
curve.name='Renamed selected curve'
assert root[c.TARGET]==curve
expected=a.export_data(root);root_name=root.name
ctx.preferences.filepaths.save_version=0
out=ROOT/'test_output/curve_button';out.mkdir(exist_ok=True)
path=out/('follow-'+os.environ.get('NMS_COLOR_TEST_LABEL','native')+'.blend')
bpy.ops.wm.save_as_mainfile(filepath=str(path));bpy.ops.wm.open_mainfile(filepath=str(path))
root=bpy.data.objects[root_name];curve=root[c.TARGET];ctx=bpy.context
assert a.export_data(root)==expected
assert abs(json.loads(root[c.STATE])['phase']-math.pi/2)<1e-6
select(root,curve);bpy.ops.nms_text.follow_curve()
assert len(a.export_data(root)['Objects'])==len(expected['Objects'])
# Updating artwork rebuilds on the remembered curve, never compounds the bend.
cfg=json.loads(root[icons.CONFIG]);icons.replace(ctx,root,cfg)
assert c.STATE in root and root[c.TARGET]==curve
assert abs(json.loads(root[c.STATE])['phase']-math.pi/2)<1e-6
new_parts=a.managed_parts(root);before=set(bpy.data.objects);snapshot=a.export_data(root)
with patch.object(c,'follow',side_effect=ValueError('deliberate staging failure')):
    try:icons.replace(ctx,root,cfg);assert False
    except ValueError:pass
assert set(bpy.data.objects)==before and a.export_data(root)==snapshot
# Undo and redo the actual button.
select(root);bpy.ops.nms_text.restore_flat();name=root.name
flat=a.export_data(root);select(root,curve);ctx.preferences.edit.use_global_undo=True
bpy.ops.ed.undo_push(message='Before follow')
assert bpy.ops.nms_text.follow_curve()=={'FINISHED'}
bent=a.export_data(root);bpy.ops.ed.undo_push(message='After follow')
assert bpy.ops.ed.undo()=={'FINISHED'}
root=bpy.data.objects[name];assert a.export_data(root)==flat and c.STATE not in root
assert bpy.ops.ed.redo()=={'FINISHED'}
root=bpy.data.objects[name];assert a.export_data(root)==bent and c.STATE in root
a.unregister()
print('FOLLOW_CURVE_SELECTION_NATIVE_PASSED',bpy.app.version_string,provider,flush=True)
