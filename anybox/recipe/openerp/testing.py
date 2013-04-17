"""Utilities for unit tests."""
import os
import unittest
import sys
import shutil
from tempfile import mkdtemp
from zc.buildout.easy_install import Installer
from . import vcs
from . import utils

COMMIT_USER_NAME = 'Test'
COMMIT_USER_EMAIL = 'test@example.org'
COMMIT_USER_FULL = '%s %s' % (COMMIT_USER_NAME, COMMIT_USER_EMAIL)


class FakeRepo(vcs.base.BaseRepo):

    log = []

    log_std_options = True

    vcs_control_dir = '.fake'

    revision = 'fakerev'

    name = 'fakevcs'  # for pip.vcs.VersionSupport registration

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

    def archive(self, target):
        utils.mkdirp(target)
        with open(os.path.join(target, '.fake_archival.txt'), 'w') as f:
            f.write(str(self.revision))


vcs.SUPPORTED['fakevcs'] = FakeRepo
from pip.vcs import vcs as pip_vcs
pip_vcs.register(FakeRepo)  # for tests around gp.vcsdevelop


def get_vcs_log():
    return FakeRepo.log


def clear_vcs_log():
    FakeRepo.log = []


class RecipeTestCase(unittest.TestCase):
    """A base setup for tests of recipe classes"""

    def setUp(self):
        b_dir = self.buildout_dir = mkdtemp('test_oerp_base_recipe')
        eggs_dir = os.path.join(b_dir, 'eggs')
        os.mkdir(eggs_dir)
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
            'eggs-directory': eggs_dir,
            'develop-eggs-directory': develop_dir,
            'python': 'main_python',
        }

        self.buildout['main_python'] = dict(executable=sys.executable)

        # temporary monkey patch of easy_install to avoid actual requests to
        # PyPI (offline mode currently does not protect against that, even
        # though I checked that it is recognized by zc.recipe.egg
        # TODO this does not seem to really work in some context
        # (Debian wheezy buildslave in a virtualenv, with zc.recipe.egg 2.0.0a3
        # we see nose being downloaded several times)
        self.unreachable_distributions = set()
        Installer._orig_obtain = Installer._obtain

        def _obtain(inst, requirement, source=None):
            if requirement.project_name in self.unreachable_distributions:
                return None
            return inst._orig_obtain(requirement, source=source)
        Installer._obtain = _obtain

    def tearDown(self):
        clear_vcs_log()
        shutil.rmtree(self.buildout_dir)
        Installer._obtain = Installer._orig_obtain
