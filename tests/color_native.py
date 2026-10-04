"""Real native factories: colour exports, legacy icons, undo and failed updates.

Run in factory-startup background Blender with the requested dependency provider.
No game/save writes; optional renders and .blend live under test_output only.
"""
import json
import importlib
import os
import sys
from pathlib import Path
from unittest.mock import patch
import addon_utils
import bpy
from mathutils import Matrix

assert bpy.app.background
ROOT=Path(__file__).resolve().parents[1]
if '--installed' not in sys.argv:sys.path.insert(0,str(ROOT))
sys.path.insert(0,str(ROOT/'tests'))
from native_bootstrap import enable_dependencies
host_name=enable_dependencies()
host_module=importlib.import_module(host_name)
requested_host=os.environ.get('NMS_TEXT_TEST_LEGACY')
if requested_host:
    assert Path(host_module.__file__).resolve().is_relative_to(Path(requested_host).resolve()),'Wrong Base Builder checkout loaded'
forge=os.environ.get('NMS_COLOR_TEST_FORGE','bl_ext.user_default.charon_forge')
forge_path=os.environ.get('NMS_COLOR_TEST_FORGE_PATH')
if forge_path:sys.path.insert(0,forge_path)
if '--forge' in sys.argv:
    assert addon_utils.enable(forge,default_set=True) is not None
    assert forge in bpy.context.preferences.addons
import nms_text_generator as a
from nms_text_generator import icon_ui as icons,color_match
a.register();ctx=bpy.context;s=ctx.scene.nms_icon_settings
assert not s.match_colors and not s.include_station
s.match_colors=True
assert bpy.ops.nms_icon.import_svg(filepath=str(ROOT/'tests/fixtures/icon_colors.svg'))=={'FINISHED'}
s.accuracy=40;s.max_parts=300
result=icons.analyze(s)
assert result['color_count']==4
assert result['coverage']>.97 and result['part_count']<=300
legacy=dict(icons.config(s));legacy.pop('match_colors');legacy.pop('include_station')
icons.load(s,legacy);assert not s.match_colors
old=icons.create(ctx,legacy)
assert len({int(p['UserData']) for p in a.managed_parts(old)})==1
assert bpy.ops.nms_icon.edit()=={'FINISHED'} and not s.match_colors
icons.load(s,dict(legacy,match_colors=True,include_station=False))
text=a.create_text(ctx,a.config_from_settings(ctx.scene.nms_text_settings))
text_before=a.export_data(text)
summary=[]
for pid in ('BUILDFLATPANEL','STORAGEPANEL'):
    s.panel_type=pid;s.match_colors=True
    root=icons.create(ctx,icons.config(s));parts=a.managed_parts(root)
    records=a.export_data(root)['Objects']
    assert len(records)==result['part_count']
    assert [int(o['UserData']) for o in records]==result['panel_userdata']
    assert len({int(o['UserData']) for o in records})==4
    assert all(o['ObjectID']=='^'+pid for o in records)
    for obj in parts:
        a.check_matrix(obj.matrix_world)
        assert obj.material_slots and not obj.modifiers and obj.get('ObjectID')==pid
    # All panels have one positive uniform scale. The tiny overlap ordering
    # is bounded independently of part count and is identical for both faces.
    depths=[]
    for obj in parts:
        scale=obj.matrix_basis.to_scale().x
        face=(0,a.panels.FLAT_FACE_Y,0) if pid=='BUILDFLATPANEL' else a.panels.STORAGE_FACE_CENTER
        from mathutils import Vector
        depths.append((obj.matrix_basis@Vector(face)).z)
    assert min(depths)>=s.face_offset-1e-5
    assert max(depths)<=s.face_offset+s.height*.002+1e-5
    # A continuous backing really spans the inset, whose native face protrudes.
    overlay_source='<svg><rect width="100" height="80" fill="red"/><rect x="8" y="8" width="84" height="64" fill="blue"/></svg>'
    overlay_data=dict(icons.config(s),source=overlay_source,source_name='Overlay depth test',accuracy=100,max_parts=100)
    overlay_fit=icons.fitted(overlay_source,100,100,True)
    assert overlay_fit['layered'] and overlay_fit['part_count']<100
    overlay=icons.create(ctx,overlay_data)
    background=color_match.nearest((1,0,0))['user_data'];foreground=color_match.nearest((0,0,1))['user_data']
    surface={background:[],foreground:[]}
    from mathutils import Vector
    for obj in a.managed_parts(overlay):
        face=(0,a.panels.FLAT_FACE_Y,0) if pid=='BUILDFLATPANEL' else a.panels.STORAGE_FACE_CENTER
        surface[int(obj['UserData'])].append((obj.matrix_basis@Vector(face)).z)
    assert min(surface[foreground])-max(surface[background])>1e-5
    root.matrix_world=Matrix.Translation((2,4,8))@Matrix.Rotation(.25,4,'Z')@Matrix.Scale(1.4,4)
    ctx.view_layer.update();matrix=root.matrix_world.copy()
    before={o.as_pointer() for o in bpy.data.objects};config=root[icons.CONFIG]
    # Unsupported colour paint cannot damage an existing icon or selection.
    try:icons.replace(ctx,root,dict(icons.config(s),source='<svg><rect width="10" height="10" fill="url(#g)"/></svg>'));assert False
    except ValueError:pass
    assert before=={o.as_pointer() for o in bpy.data.objects} and root[icons.CONFIG]==config
    backend=a.get_builder(pid);factory=backend.add_part;calls=[0]
    def fail(*args,**kwargs):
        calls[0]+=1
        if calls[0]>2:raise RuntimeError('factory failure')
        return factory(*args,**kwargs)
    with patch.object(backend,'add_part',side_effect=fail):
        try:icons.replace(ctx,root,icons.config(s));assert False
        except RuntimeError:pass
    assert before=={o.as_pointer() for o in bpy.data.objects} and root[icons.CONFIG]==config
    icons.replace(ctx,root,icons.config(s));assert root.matrix_world==matrix
    assert a.export_data(text)==text_before
    # Station codes remain exported through providers with an older CSV too.
    for station in color_match.catalog()['palettes'][115:]:
        rgb=color_match.srgb(station['p']);paint='#'+''.join(f'{round(c*255):02x}' for c in rgb)
        if color_match.nearest(color_match.parse_color(paint)[0],True)['user_data']>=115:break
    station_data=dict(icons.config(s),include_station=True,source=f'<svg><rect width="20" height="10" fill="{paint}"/></svg>')
    station_root=icons.create(ctx,station_data)
    expected=color_match.nearest(color_match.parse_color(paint)[0],True)['user_data']
    assert expected>=115
    assert {int(o['UserData']) for o in a.export_data(station_root)['Objects']}=={expected}
    # Test old and colour settings survive saving and reopening the same file.
    label=os.environ.get('NMS_COLOR_TEST_LABEL','native')
    out=ROOT/'test_output/color_matching';out.mkdir(parents=True,exist_ok=True)
    path=out/f'{label}-{pid}.blend'
    bpy.context.preferences.filepaths.save_version=0
    bpy.ops.wm.save_as_mainfile(filepath=str(path))
    root_name=root.name;original_export=a.export_data(root)
    bpy.ops.wm.open_mainfile(filepath=str(path));ctx=bpy.context
    root=bpy.data.objects[root_name];a.select_parts(ctx,root)
    assert bpy.ops.nms_icon.edit()=={'FINISHED'}
    s=ctx.scene.nms_icon_settings
    assert s.match_colors and a.export_data(root)==original_export
    summary.append({'panel':pid,'parts':result['part_count'],'colors':result['color_count'],'coverage':result['coverage']})
    print('COLOR_NATIVE_PANEL_PASS',pid,flush=True)
    # The previous object handles were invalidated by open_mainfile.
    text=next(o for o in bpy.data.objects if o.get(a.ROOT));text_before=a.export_data(text)
    old=next(o for o in bpy.data.objects if o.get(icons.ROOT) and not json.loads(o[icons.CONFIG]).get('match_colors',False))

summary={'blender':bpy.app.version_string,'provider':type(a.get_builder()).__name__,
         'host':host_name,'host_source':host_module.__file__,'forge_enabled':forge in bpy.context.preferences.addons,'checks':summary}
(out/f'{label}.json').write_text(json.dumps(summary,indent=2),encoding='utf-8')
a.unregister()
print('COLOR_NATIVE_ROUNDTRIP_ROLLBACK_LEGACY_PASSED',json.dumps(summary),flush=True)
