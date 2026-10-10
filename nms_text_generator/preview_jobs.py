"""Isolated numerical preview jobs. This module never imports Blender APIs."""
import atexit
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import time

_reporter = None


def report(stage):
    if _reporter is not None:
        _reporter(stage)


def python_binary():
    if Path(sys.executable).stem.lower().startswith('python'):
        return sys.executable
    for candidate in (Path(sys.prefix)/'bin/python.exe', Path(sys.prefix)/'bin/python3'):
        if candidate.is_file():
            return str(candidate)
    raise RuntimeError('The bundled Python runtime could not be found for previews.')


class SimplificationNeeded(ValueError):
    pass


def fit_icon(args, preflight=False, rebuild=False, strengthen=False):
    """Try the vector fit, then one bounded feature trace on recoverable failure."""
    from . import color_match,icon_fit,svg_outline
    args=list(args);source=args[0];info={}
    def fit():
        return (color_match.fit_svg(*args[:3],args[4],args[5]) if args[3]
                else icon_fit.fit_svg(*args[:3]))
    try:
        if rebuild:raise ValueError('Rebuild requested')
        if preflight:
            if args[3]:color_match.preflight(source,args[4],allow_simplify=False)
            else:icon_fit.read_outline(source,allow_simplify=False)
        return fit()
    except icon_fit.SimplificationRequired:
        raise
    except ValueError as original:
        report('Tracing SVG features')
        try:args[0],info=svg_outline.rebuild_svg(source,with_colors=args[3],strengthen=strengthen)
        except ValueError as recovery:
            raise ValueError(f'{original} Rebuild could not trace this artwork: {recovery}') from recovery
        if preflight:
            raise icon_fit.SimplificationRequired('Normal import failed. Choose Simplify & Import to rebuild the visible SVG features. Small details may change.')
        result=fit()
        return {**result,**info,'_rebuilt_source':args[0]}


class Job:
    def __init__(self, key, payload):
        self.key = key
        self.started = time.monotonic()
        self.stage = 'Starting preview'
        self.directory = Path(tempfile.mkdtemp(prefix='nmscribe-preview-'))
        request = self.directory/'request.json'
        request.write_text(json.dumps(payload), encoding='utf-8')
        env = dict(os.environ, OPENBLAS_NUM_THREADS='1', OMP_NUM_THREADS='1')
        try:
            self.process = subprocess.Popen(
                [python_binary(), str(Path(__file__).resolve()), '--worker', str(request)],
                stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                env=env, creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
        except Exception:
            shutil.rmtree(self.directory, ignore_errors=True)
            raise

    def poll(self):
        try:
            self.stage = json.loads((self.directory/'progress.json').read_text(encoding='utf-8'))['stage']
        except (OSError, ValueError):
            pass
        return self.process.poll() is not None

    def result(self):
        path = self.directory/'result.json'
        if not path.exists():
            raise RuntimeError('Preview worker stopped before completing. Adjust a setting to retry.')
        data = json.loads(path.read_text(encoding='utf-8'))
        if data.get('simplification_required'):raise SimplificationNeeded(data['error'])
        if 'error' in data:
            raise ValueError(data['error'])
        result = data['result']
        if (self.directory/'preview.npy').exists():
            import numpy as np
            result['preview'] = np.load(self.directory/'preview.npy', allow_pickle=False)
        return result

    def close(self):
        if self.process.poll() is None:
            self.process.terminate()
            try:
                self.process.wait(timeout=.2)
            except subprocess.TimeoutExpired:
                self.process.kill()
                self.process.wait(timeout=1)
        shutil.rmtree(self.directory, ignore_errors=True)


class Jobs:
    def __init__(self):
        self.active = {}
        atexit.register(self.close)

    def start(self, owner, key, payload):
        current = self.active.get(owner)
        if current and current.key == key:
            return current
        self.cancel(owner)
        current = Job(key, payload)
        self.active[owner] = current
        return current

    def cancel(self, owner):
        job = self.active.pop(owner, None)
        if job:
            job.close()

    def close(self):
        for owner in list(self.active):
            self.cancel(owner)


def worker(request):
    # Import only pure modules, never the add-on's bpy-dependent __init__.
    import types
    import numpy as np
    package = types.ModuleType('nmscribe_worker')
    package.__path__ = [str(Path(__file__).parent)]
    sys.modules[package.__name__] = package
    from nmscribe_worker import preview_jobs, color_match, icon_fit, layout
    directory = request.parent
    def progress(stage):
        temporary = directory/'progress.tmp'
        temporary.write_text(json.dumps({'stage': stage}), encoding='utf-8')
        try:temporary.replace(directory/'progress.json')
        except OSError:pass  # A simultaneous UI read may briefly hold the file on Windows.
    preview_jobs._reporter = progress
    try:
        data = json.loads(request.read_text(encoding='utf-8'))
        progress('Reading SVG' if data['kind'] == 'icon' else 'Laying out text')
        if data['kind'] == 'icon':
            args = data['args']
            result = preview_jobs.fit_icon(args,preflight=data.get('preflight',False),
                                           rebuild=data.get('rebuild',False),strengthen=data.get('strengthen',False))
            np.save(directory/'preview.npy', result.pop('preview'), allow_pickle=False)
        else:
            result = layout.plan(**data['args'])
            result = {key: result[key] for key in ('part_count', 'character_count')}
            result['max_parts_per_character'] = layout.library(data['args'].get('font','FUTURE_Z'))['max_parts_per_character']
        output = {'result': result}
    except icon_fit.SimplificationRequired as exc:
        output = {'error':str(exc),'simplification_required':True}
    except Exception as exc:
        output = {'error': str(exc)}
    (directory/'result.json').write_text(json.dumps(output, default=lambda obj: obj.tolist()), encoding='utf-8')


if __name__ == '__main__':
    worker(Path(sys.argv[2]))
