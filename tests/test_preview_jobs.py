import sys
import time
import types
import unittest
from pathlib import Path

pkg = types.ModuleType('preview_test_package')
pkg.__path__ = [str(Path(__file__).resolve().parents[1]/'nms_text_generator')]
sys.modules[pkg.__name__] = pkg
from preview_test_package.preview_jobs import Jobs


class PreviewJobsTests(unittest.TestCase):
    def setUp(self):
        self.jobs = Jobs()

    def tearDown(self):
        self.jobs.close()

    def finish(self, job):
        deadline = time.monotonic()+40
        ticks = 0
        while not job.poll():
            self.assertLess(time.monotonic(), deadline)
            ticks += 1
            time.sleep(.02)
        self.assertGreater(ticks, 0)
        return job.result()

    def test_text_result_and_error_are_delivered_without_blocking(self):
        job = self.jobs.start('text', ('NMS',), {'kind':'text','args':{'text':'NMS','font':'FUTURE_Z'}})
        self.assertEqual(self.finish(job)['character_count'], 3)
        job = self.jobs.start('text', ('bad',), {'kind':'text','args':{'text':'☃','font':'FUTURE_Z'}})
        with self.assertRaisesRegex(ValueError, 'Unsupported characters'):
            self.finish(job)

    def test_replacement_terminates_stale_job_and_removes_temporary_files(self):
        source = (Path(__file__).parent/'fixtures/icon_layered_emblem.svg').read_text()
        old = self.jobs.start('scene', 1, {'kind':'icon','args':[source,100,600,True,False,'{}']})
        new = self.jobs.start('scene', 2, {'kind':'text','args':{'text':'ABC'}})
        self.assertIsNotNone(old.process.poll())
        self.assertFalse(old.directory.exists())
        self.assertIs(self.jobs.start('scene', 2, {}), new)
        self.assertEqual(self.finish(new)['character_count'], 3)
        self.jobs.close()
        self.assertFalse(new.directory.exists())

    def test_icon_roundtrip_keeps_array_and_budget(self):
        job = self.jobs.start('icon', 3, {'kind':'icon','args':['<svg><rect width="20" height="10" fill="red"/></svg>',50,30,True,False,'{}']})
        result = self.finish(job)
        self.assertEqual(result['preview'].shape, (result['resolution'],)*2+(4,))
        self.assertLessEqual(result['part_count'], 30)
        self.assertGreater(result['coverage'], .98)
