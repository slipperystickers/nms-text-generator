"""Real curve evaluation, native generation, saved edits and rollback."""
import json,sys,os
from pathlib import Path
import bpy
from mathutils import Matrix,Vector
ROOT=Path(__file__).resolve().parents[1]
if '--installed' not in sys.argv:sys.path.insert(0,str(ROOT))
sys.path.insert(0,str(ROOT/'tests'))
from native_bootstrap import enable_dependencies
enable_dependencies()
import nms_text_generator as a
from nms_text_generator import curve_layout as curves,icon_ui as icons
a.register();ctx=bpy.context

def curve(kind,closed=False):
    data=bpy.data.curves.new('Curve test '+kind,'CURVE');data.dimensions='3D'
    spline=data.splines.new(kind)
    coords=[(0,0,0),(10,2,1),(20,6,4),(30,10,4)]
    if kind=='BEZIER':
        spline.bezier_points.add(3)
        for p,co in zip(spline.bezier_points,coords):p.co=co;p.handle_left_type='AUTO';p.handle_right_type='AUTO'
    else:
        spline.points.add(3)
        for p,co in zip(spline.points,coords):p.co=(*co,1)
        if kind=='NURBS':spline.order_u=3;spline.use_endpoint_u=True
    spline.use_cyclic_u=closed
    data.bevel_depth=.2;data.extrude=.1
    obj=bpy.data.objects.new(data.name,data);ctx.scene.collection.objects.link(obj)
    obj.matrix_world=Matrix.Translation((3,5,7))@Matrix.Rotation(.4,4,'Z')@Matrix.Diagonal((1.2,.8,1.4,1))
    ctx.view_layer.update();return obj

paths=[]
for kind,closed in [('BEZIER',False),('POLY',False),('POLY',True),('NURBS',False),('NURBS',True)]:
    obj=curve(kind,closed);before=set(bpy.data.objects);data_count=len(bpy.data.curves)
    path=curves.Path(ctx,dict(curves.DEFAULTS,curve_name=obj.name,orientation='FLAT'))
    assert set(bpy.data.objects)==before and len(bpy.data.curves)==data_count
    assert obj.data.bevel_depth>.19 and path.length>0
    for distance in (0,path.length*.25,path.length*.6,path.length):a.check_matrix(path.matrix@path.frame(distance))
    assert (path.frame(0).translation-path.points[0]).length<1e-6
    assert (path.frame(path.length).translation-path.points[-1]).length<1e-6
    paths.append(obj)

obj=paths[0];s=ctx.scene.nms_text_settings
s.text='CURVE<br>TEST';s.use_curve=True;s.curve_name=obj.name;s.curve_fit=True;s.orientation='UPRIGHT'
for pid in ('BUILDFLATPANEL','STORAGEPANEL'):
    s.panel_type=pid
    root=a.create_text(ctx,a.config_from_settings(s));records=a.export_data(root)
    assert len(records['Objects'])==a.make_plan(a.config_from_settings(s))['part_count']
    assert len({tuple(round(v,2) for v in p.matrix_world.to_quaternion()) for p in a.managed_parts(root)})>2
    for p in a.managed_parts(root):a.check_matrix(p.matrix_world)
    original=root.matrix_world.copy();a.replace_text(ctx,root,a.config_from_settings(s));assert root.matrix_world==original

i=ctx.scene.nms_icon_settings;i.match_colors=True
icons.import_source(ctx,(ROOT/'tests/fixtures/icon_colors.svg').read_text(),'Colours')
i.use_curve=True;i.curve_name=obj.name;i.curve_fit=True;i.max_parts=100
i.color_overrides='{"#EB5B24":150}'
result=icons.analyze(i);assert 150 in result['panel_userdata']
icons.create(ctx,icons.config(i))  # Legacy recipe API remains loadable.
root=icons.selected(ctx);assert [int(o['UserData']) for o in a.export_data(root)['Objects']]==result['panel_userdata']
old_export=a.export_data(root);old_config=root[icons.CONFIG];before=set(bpy.data.objects)
try:icons.replace(ctx,root,dict(icons.config(i),curve_name='Missing curve'));assert False
except ValueError:pass
assert set(bpy.data.objects)==before and root[icons.CONFIG]==old_config and a.export_data(root)==old_export
# Too-short paths fail before any panels are created.
try:a.create_text(ctx,dict(a.config_from_settings(s),height=10000,curve_fit=False));assert False
except ValueError:pass
assert set(bpy.data.objects)==before
# Dialog stages choices; prepare does not change the settings.
class StagedChoices(bpy.types.PropertyGroup):
    rows:bpy.props.CollectionProperty(type=icons.NMSICON_ColorChoice)
    include_station:bpy.props.BoolProperty()
    source_hash:bpy.props.StringProperty()
bpy.utils.register_class(StagedChoices)
bpy.types.WindowManager.curve_test_choices=bpy.props.PointerProperty(type=StagedChoices)
op=ctx.window_manager.curve_test_choices
icons.NMSICON_OT_colors.prepare(op,i);assert i.color_overrides=='{"#EB5B24":150}'
red=next(row for row in op.rows if row.source_key=='#EB5B24')
assert red.family=='STATION' and red.palette=='150'
red.family='LEGACY';red.palette='8'
assert i.color_overrides=='{"#EB5B24":150}'
assert icons.NMSICON_OT_colors.execute(op,ctx)=={'FINISHED'} and json.loads(i.color_overrides)['#EB5B24']==8
del bpy.types.WindowManager.curve_test_choices;bpy.utils.unregister_class(StagedChoices)
assert 8 in icons.analyze(i)['panel_userdata']
icons.replace(ctx,root,icons.config(i));expected=a.export_data(root)
out=ROOT/'test_output/curve_layout';out.mkdir(parents=True,exist_ok=True)
name=root.name;curve_name=obj.name;bpy.context.preferences.filepaths.save_version=0
path=out/('curved-text-icons-'+os.environ.get('NMS_COLOR_TEST_LABEL','native')+'.blend')
bpy.ops.wm.save_as_mainfile(filepath=str(path))
bpy.ops.wm.open_mainfile(filepath=str(path))
root=bpy.data.objects[name];a.select_parts(bpy.context,root)
assert bpy.ops.nms_icon.edit()=={'FINISHED'}
i=bpy.context.scene.nms_icon_settings
assert i.use_curve and i.curve_name==curve_name
assert json.loads(i.color_overrides)['#EB5B24']==8 and a.export_data(root)==expected
icons.import_source(bpy.context,(ROOT/'tests/fixtures/icon_colors.svg').read_text(),'New import');assert i.color_overrides=='{}'
a.unregister();print('CURVE_NATIVE_CHOICES_ROUNDTRIP_ROLLBACK_PASSED',bpy.app.version_string,flush=True)
