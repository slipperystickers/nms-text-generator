"""Exercise the real preview callbacks with a clock and host, without Blender."""
import ast
import hashlib
from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest.mock import Mock


SOURCE = Path(__file__).resolve().parents[1]/'nms_text_generator/icon_ui.py'
CALLBACKS = {'key', 'changed', 'request_preview', 'refresh'}
TREE = ast.parse(SOURCE.read_text(encoding='utf-8'))
CODE = compile(ast.Module(body=[node for node in TREE.body
                               if isinstance(node, ast.FunctionDef) and node.name in CALLBACKS],
                          type_ignores=[]), str(SOURCE), 'exec')


class FakeJobs:
    def __init__(self):
        self.active = {}
        self.starts = []
        self.cancelled = []

    def start(self, owner, key, payload):
        job = SimpleNamespace(key=key, ready=False, result=Mock())
        job.poll = lambda: job.ready
        self.active[owner] = job
        self.starts.append((owner, key, payload))
        return job

    def cancel(self, owner):
        self.cancelled.append(owner)
        self.active.pop(owner, None)


class PreviewSchedulingTests(unittest.TestCase):
    def setUp(self):
        self.now = 10.0
        self.settings = SimpleNamespace(source='<svg/>', accuracy=100, max_parts=300,
                                        match_colors=False, include_station=False,
                                        color_overrides='{}', status='')
        self.scene = SimpleNamespace(name='Scene', nms_icon_settings=self.settings)
        self.context = SimpleNamespace(scene=self.scene)
        self.registered = []
        timers = SimpleNamespace(is_registered=lambda callback: bool(self.registered),
                                 register=lambda callback, **options:
                                 self.registered.append((callback, options)))
        self.jobs = FakeJobs()
        self.state = {
            'time': SimpleNamespace(monotonic=lambda: self.now),
            'hashlib': hashlib,
            'color_match': SimpleNamespace(overrides_json=lambda value: value),
            'bpy': SimpleNamespace(app=SimpleNamespace(timers=timers),
                                   data=SimpleNamespace(scenes={self.scene.name: self.scene})),
            '_loading': False, '_errors': set(), '_dirty': {}, '_imports': {},
            '_jobs': self.jobs, '_cache': {}, '_import_errors': {},
            'redraw': Mock(), 'analyze': Mock(),
            'fitted': Mock(side_effect=AssertionError('Fitting blocked a preview callback')),
            'preview_jobs': SimpleNamespace(SimplificationNeeded=ValueError),
        }
        # Importing icon_ui would import bpy. Compile its actual callbacks instead
        # of copying their implementation; only the clock and host are simulated.
        exec(CODE, self.state)

    def change_accuracy(self, accuracy):
        self.settings.accuracy = accuracy
        self.state['changed'](self.settings, self.context)

    def finish_debounce(self):
        self.now = self.state['_dirty'][self.scene.name]+.001
        self.state['refresh']()

    def test_slider_drag_coalesces_to_one_latest_value_without_early_fit(self):
        for accuracy in range(100, 59, -1):
            self.now += .005
            self.change_accuracy(accuracy)
            self.state['refresh']()

        self.assertEqual(len(self.registered), 1)
        self.assertEqual(self.jobs.starts, [])
        self.state['analyze'].assert_not_called()
        self.state['fitted'].assert_not_called()
        self.finish_debounce()

        self.assertEqual(len(self.jobs.starts), 1)
        owner, key, payload = self.jobs.starts[0]
        self.assertEqual(owner, self.scene.name)
        self.assertEqual(key, self.state['key'](self.settings))
        self.assertEqual(payload['args'][1], 60)
        self.state['analyze'].assert_not_called()
        self.state['fitted'].assert_not_called()

    def test_repeated_draw_requests_do_not_postpone_slider_deadline(self):
        self.change_accuracy(60)
        deadline = self.state['_dirty'][self.scene.name]
        for _ in range(10):
            self.now += .01
            self.state['request_preview'](self.scene)
            self.assertEqual(self.state['_dirty'][self.scene.name], deadline)

        self.assertEqual(len(self.registered), 1)
        self.finish_debounce()
        self.assertEqual(len(self.jobs.starts), 1)

    def test_completed_stale_result_is_discarded_before_latest_job_runs(self):
        self.change_accuracy(100)
        self.finish_debounce()
        old = self.jobs.active[self.scene.name]
        old.ready = True

        self.change_accuracy(60)
        self.state['refresh']()
        self.assertEqual(self.jobs.cancelled, [self.scene.name])
        old.result.assert_not_called()
        self.state['analyze'].assert_not_called()
        self.assertEqual(self.state['_cache'], {})
        self.assertEqual(len(self.jobs.starts), 1)

        self.finish_debounce()
        self.assertEqual(len(self.jobs.starts), 2)
        self.assertEqual(self.jobs.starts[-1][2]['args'][1], 60)
        self.assertEqual(self.jobs.active[self.scene.name].key,
                         self.state['key'](self.settings))


if __name__ == '__main__':
    unittest.main()
