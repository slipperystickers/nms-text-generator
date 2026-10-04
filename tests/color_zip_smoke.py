"""Verify the final colour feature from a fresh, exact installer extraction."""
import runpy
import sys
import tempfile
from pathlib import Path
from zipfile import ZipFile
ROOT=Path(__file__).resolve().parents[1]
with tempfile.TemporaryDirectory(prefix='nmscribe-color-clean-') as folder:
    with ZipFile(ROOT/'dist/NMS_Text_Generator_2.2.8.zip') as z:
        assert z.testzip() is None
        assert all(not Path(n).is_absolute() and '..' not in Path(n).parts for n in z.namelist())
        z.extractall(folder)
    sys.path.insert(0,folder);sys.argv.append('--installed')
    runpy.run_path(str(ROOT/'tests/color_native.py'),run_name='__main__')
    runpy.run_path(str(ROOT/'tests/curve_native.py'),run_name='__main__')
    runpy.run_path(str(ROOT/'tests/follow_curve_native.py'),run_name='__main__')
    import nms_text_generator as addon
    assert Path(addon.__file__).resolve().is_relative_to(Path(folder).resolve())
print('FINAL_COLOR_CLEAN_ZIP_PASSED',flush=True)
