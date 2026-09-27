"""Provider changes and matching native exports; disposable Blender only."""
import sys
from pathlib import Path
import addon_utils, bpy
from mathutils import Matrix
assert bpy.app.background
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
HOST='bl_ext.user_default.no_mans_sky_base_builder'
FORGE='bl_ext.user_default.charon_forge'

# Forge may be enabled first; its normal hook callback must handle the host
# arriving later. NMS Text must not install patches or register dependencies.
assert addon_utils.enable(FORGE,default_set=True) is not None
assert addon_utils.enable(HOST,default_set=True) is not None
import nms_text_generator as a
a.register()
assert isinstance(a.get_builder(),a.backend.SplitBackend)
addon_utils.disable(FORGE,default_set=True)
assert isinstance(a.get_builder(),a.backend.StandardBackend)

config=dict(a.config_from_settings(bpy.context.scene.nms_text_settings),font='VECTOR',text='AIR 07')
standard={}; roots=[]; matrices={}
for pid in ('BUILDFLATPANEL','STORAGEPANEL'):
    root=a.create_text(bpy.context,dict(config,panel_type=pid))
    roots.append(root)
    standard[pid]=a.export_data(root)['Objects']
    matrices[pid]=[o.matrix_world.copy() for o in a.managed_parts(root)]
    assert all(not o.data.name.startswith('NMS_HR_') for o in a.managed_parts(root))

assert addon_utils.enable(FORGE,default_set=True) is not None
for pid,root in zip(('BUILDFLATPANEL','STORAGEPANEL'),roots):
    assert a.export_data(root)['Objects']==standard[pid] # enabling does not mutate existing signs
    updated=a.replace_text(bpy.context,root,dict(config,panel_type=pid))
    current=a.export_data(root)['Objects']
    assert len(current)==len(standard[pid])
    for old,new,obj,matrix in zip(standard[pid],current,a.managed_parts(root),matrices[pid]):
        for key in ('ObjectID','UserData'):assert old[key]==new[key]
        for key in ('Position','Up','At'):
            assert max(abs(x-y) for x,y in zip(old[key],new[key]))<2e-5
        assert max(abs(matrix[i][j]-obj.matrix_world[i][j]) for i in range(4) for j in range(4))<2e-5
        assert obj.data.name.startswith('NMS_HR_') and obj.material_slots

addon_utils.disable(FORGE,default_set=True)
assert isinstance(a.get_builder(),a.backend.StandardBackend)
assert not getattr(a.get_builder().BUILDER,'use_high_res',False)
for root in roots:
    assert a.export_data(root)['Objects']
    a.replace_text(bpy.context,root,dict(config,panel_type='BUILDFLATPANEL'))
    # Base Builder may reuse a native HD mesh already cached in this scene.
    # Disabling Forge must not remove that mesh or require Forge to keep editing.
    assert all(o.get('ObjectID')=='BUILDFLATPANEL' and o.material_slots for o in a.managed_parts(root))
print('BACKEND_LIFECYCLE_AND_EXPORT_PARITY_PASSED',flush=True)
