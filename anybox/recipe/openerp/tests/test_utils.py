import unittest
import tempfile
import shutil
import os

from ..utils import working_directory_keeper


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
