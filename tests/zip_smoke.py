"""Run native tests against a fresh extraction of the installer ZIP."""
import runpy,sys,tempfile
from pathlib import Path
from zipfile import ZipFile
ROOT=Path(__file__).resolve().parents[1]
with tempfile.TemporaryDirectory(prefix='nms-text-clean-install-') as folder:
    with ZipFile(ROOT/'dist'/'NMS_Text_Generator_2.0.0.zip') as z:
        assert all(not Path(n).is_absolute() and '..' not in Path(n).parts for n in z.namelist())
        z.extractall(folder)
    sys.path.insert(0,folder)
    sys.argv.append('--installed')
    runpy.run_path(str(ROOT/'tests'/'storage_defaults.py'),run_name='__main__')
    runpy.run_path(str(ROOT/'tests'/'blender_smoke.py'),run_name='__main__')
    runpy.run_path(str(ROOT/'tests'/'blender_panels.py'),run_name='__main__')
    runpy.run_path(str(ROOT/'tests'/'icon_smoke.py'),run_name='__main__')
    import nms_text_generator
    assert Path(nms_text_generator.__file__).resolve().is_relative_to(Path(folder).resolve())
    print('CLEAN_ZIP_INSTALL_PASSED',flush=True)
