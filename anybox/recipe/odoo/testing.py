"""Utilities for unit tests."""
import os
import unittest
import sys
import shutil
import subprocess
from tempfile import mkdtemp
from UserDict import UserDict
from zc.buildout.easy_install import Installer

from . import vcs
from .base import BaseRecipe

COMMIT_USER_NAME = 'Test'
COMMIT_USER_EMAIL = 'test@example.org'
COMMIT_USER_FULL = '%s %s' % (COMMIT_USER_NAME, COMMIT_USER_EMAIL)


class TestingRecipe(BaseRecipe):
    """A subclass with just enough few defaults for unit testing."""

    release_filenames = {'8.0': 'blob-%s.tgz'}
    nightly_filenames = {'8.0': '8-0-nightly-%s.tbz'}
    release_dl_url = {'8.0': 'http://release.odoo.test/src/'}

    def __init__(self, buildout, name, options):
        # we need to make buildout a regular object, because some subsystems
        # will set extra attributes on it
        if isinstance(buildout, dict):
            buildout = UserDict(buildout)
        super(TestingRecipe, self).__init__(buildout, name, options)


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

    def revert(self, revision):
        self.revision = revision
        self.log.append(('revert', revision, self.target_dir))

    def parents(self, pip_compatible=False, **kwargs):
        return [self.revision]

    def archive(self, target):
        if not os.path.isdir(target):
            os.makedirs(target)
        with open(os.path.join(target, '.fake_archival.txt'), 'w') as f:
            f.write(str(self.revision))

    def is_local_fixed_revision(self, revspec):
        return revspec in getattr(self, 'fixed_revs', ())


vcs.SUPPORTED['fakevcs'] = FakeRepo
from pip.vcs import vcs as pip_vcs
pip_vcs.register(FakeRepo)  # for tests around gp.vcsdevelop


def get_vcs_log():
    return FakeRepo.log


def clear_vcs_log():
    FakeRepo.log = []


class PersistentRevFakeRepo(FakeRepo):
    """A variant of FakeRepo that still needs the directory structure around.

    Makes for a more realistic test of some conditions.
    In particular, reproduced launchpad #TODO
    """

    current_revisions = {}

    @property
    def revision(self):
        return self.__class__.current_revisions.get(self.target_dir, 'fakerev')

    @revision.setter
    def revision(self, v):
        self.__class__.current_revisions[self.target_dir] = v

    def uncommitted_changes(self):
        """This needs the directory to really exist and is controllable."""
        files = set(os.listdir(self.target_dir))
        files.discard('.fake')
        return bool(files)


vcs.SUPPORTED['pr_fakevcs'] = PersistentRevFakeRepo


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
        self.exc_distributions = {}  # distrib name -> exc to raise
        Installer._orig_obtain = Installer._obtain

        def _obtain(inst, requirement, source=None):
            if requirement.project_name in self.unreachable_distributions:
                return None
            exc = self.exc_distributions.get(requirement.project_name)
            if exc is not None:
                raise exc
            return inst._orig_obtain(requirement, source=source)
        Installer._obtain = _obtain

    def make_recipe(self, name='openerp', **options):
        self.recipe = TestingRecipe(self.buildout, name, options)

    def tearDown(self):
        clear_vcs_log()
        shutil.rmtree(self.buildout_dir)
        Installer._obtain = Installer._orig_obtain

        # leftover egg-info at root of the source dir (frequent cwd)
        # impairs use of this very same source dir for real-life testing
        # with a 'develop' option.
        egg_info = 'Babel.egg-info'
        if os.path.isdir(egg_info):
            shutil.rmtree(egg_info)

    def build_babel_egg(self):
        """build an egg for fake babel in buildout's eggs directory.

        Require the test case to already have a ``test_dir`` attribute
        (typically set on class with the dirname of the test)
        """
        subprocess.check_call(
            [sys.executable, 'setup.py',
             'bdist_egg',
             '-d', self.recipe.b_options['eggs-directory'],
             '-b', os.path.join(self.buildout_dir, 'build')],
            cwd=os.path.join(self.test_dir, 'fake_babel'),
            stdout=subprocess.PIPE)

    def fill_working_set(self):
        self.build_babel_egg()
        self.recipe.options['eggs'] = 'Babel'
        self.recipe.install_requirements()  # to get 'ws' attribute
