"""Utilities for unit tests."""
import os
import unittest
import sys
import shutil
from tempfile import mkdtemp
from anybox.recipe.openerp import vcs

class FakeRepo(vcs.BaseRepo):

    log = []

    log_std_options = True

    vcs_control_dir = '.fake'

    revision = 'fakerev'

    name = 'fakevcs' # for pip.vcs.VersionSupport registration

    def get_update(self, revision):
        self.revision = revision
        if not os.path.isdir(self.target_dir):
            os.mkdir(self.target_dir)
        control = os.path.join(self.target_dir, self.vcs_control_dir)
        if not os.path.isdir(control):
            os.mkdir(control)

        options = self.options.copy()
        if self.log_std_options:
            options['offline'] = self.offline
            options['clear_locks'] = self.clear_locks
        self.log.append((self.target_dir, self.url, revision, options),)

    def parents(self):
        return [self.revision]

vcs.SUPPORTED['fakevcs'] = FakeRepo
from pip.vcs import vcs
vcs.register(FakeRepo)  # for tests around gp.vcsdevelop

def get_vcs_log():
    return FakeRepo.log

def clear_vcs_log():
    FakeRepo.log = []


class RecipeTestCase(unittest.TestCase):
    """A base setup for tests of recipe classes"""

    def setUp(self):
        b_dir = self.buildout_dir = mkdtemp('test_oerp_base_recipe')
        develop_dir = os.path.join(b_dir, 'develop-eggs')
        os.mkdir(develop_dir)
        self.buildout = {}
        self.buildout['buildout'] = {
            'directory': b_dir,
            'offline': False,
            'parts-directory': os.path.join(b_dir, 'parts'),
            'bin-directory': os.path.join(b_dir, 'bin'),
            'find-links': '',
            'allow-hosts': '',
            'eggs-directory': 'eggs',
            'develop-eggs-directory': develop_dir,
            'python': 'main_python',
            }

        self.buildout['main_python'] = dict(executable=sys.executable)

    def tearDown(self):
        clear_vcs_log()
        shutil.rmtree(self.buildout_dir)

