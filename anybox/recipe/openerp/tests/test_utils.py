import unittest
import tempfile
import shutil
import os
from datetime import timedelta

from ..utils import working_directory_keeper, total_seconds


class WorkingDirectoryTestCase(unittest.TestCase):

    def setUp(self):
        self.dirpath = tempfile.mkdtemp()

    def tearDown(self):
        shutil.rmtree(self.dirpath)

    def test_ctx_manager(self):
        # warning: if this fails, then many other tests can be
        # affected, because many don't like being in /
        current = os.getcwd()
        with working_directory_keeper:
            os.chdir(self.dirpath)
            self.assertNotEqual(os.getcwd(), current)

        self.assertEqual(os.getcwd(), current)


class VariousTestCase(unittest.TestCase):

    def test_total_seconds(self):
        self.assertEqual(total_seconds(timedelta(1, 2)), 86402.0)
        self.assertEqual(total_seconds(timedelta(0, -3)), -3.0)
        self.assertEqual(total_seconds(timedelta(0, 12, 35000)), 12.035)
