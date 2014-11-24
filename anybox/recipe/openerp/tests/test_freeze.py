import os
import sys
import subprocess
from ConfigParser import ConfigParser, NoOptionError
from anybox.recipe.openerp.base import GP_VCS_EXTEND_DEVELOP
from ..testing import RecipeTestCase
from ..testing import COMMIT_USER_FULL

TEST_DIR = os.path.dirname(__file__)


class TestFreeze(RecipeTestCase):

    def build_babel_egg(self):
        """build an egg for fake babel in buildout's eggs directory."""
        subprocess.check_call(
            [sys.executable,
             os.path.join(TEST_DIR, 'fake_babel', 'setup.py'),
             'bdist_egg',
             '-d', self.recipe.b_options['eggs-directory'],
             '-b', os.path.join(self.buildout_dir, 'build')],
            stdout=subprocess.PIPE)

    def test_freeze_egg_versions(self):
        """Test that an egg requirement is properly dumped with its version.
        """
        conf = ConfigParser()
        conf.add_section('freeze')
        self.make_recipe(version='6.1-1')
        self.build_babel_egg()
        self.recipe.options['eggs'] = 'Babel'
        self.recipe.install_requirements()  # to get 'ws' attribute
        self.recipe._freeze_egg_versions(conf, 'freeze')
        try:
            version = conf.get('freeze', 'Babel')
        except NoOptionError:
            self.fail("Expected version of Babel egg not dumped !")
        self.assertTrue(version.startswith('0.123'))

    def test_freeze_egg_versions_merge(self):
        """Test that freezing of egg versions keeps eggs already dumped.

        very much similar to test_freeze_egg_versions.
        """
        conf = ConfigParser()
        conf.add_section('freeze')
        conf.set('freeze', 'some.distribution', '1.0alpha')
        self.make_recipe(version='6.1-1')
        self.build_babel_egg()
        self.recipe.options['eggs'] = 'Babel'
        self.recipe.install_requirements()  # to get 'ws' attribute
        self.recipe._freeze_egg_versions(conf, 'freeze')
        try:
            version = conf.get('freeze', 'some.distribution')
        except NoOptionError:
            self.fail("Expected version of 'some.distribution' not kept !")
        self.assertEquals(version, '1.0alpha')

    def test_freeze_egg_versions_develop(self):
        """Test that a developped requirement is not dumped in [versions].
        """
        conf = ConfigParser()
        conf.add_section('freeze')
        self.make_recipe(version='6.1-1')
        self.recipe.develop(os.path.join(TEST_DIR, 'fake_babel'))
        self.recipe.options['eggs'] = 'Babel'
        self.recipe.install_requirements()  # to get 'ws' attribute
        self.recipe._freeze_egg_versions(conf, 'freeze')
        self.assertRaises(NoOptionError, conf.get, 'freeze', 'Babel')

    def test_freeze_vcs_source(self):
        self.make_recipe(version='6.1-1')
        b_dir = self.recipe.buildout_dir
        repo_path = os.path.join(b_dir, 'custom')
        subprocess.check_call(['hg', 'init', repo_path])
        with open(os.path.join(repo_path, 'somefile'), 'w') as f:
            f.write('content')
        subprocess.check_call(['hg', '--cwd', repo_path,
                               'commit', '-A', '-m', 'somerev',
                               '-u', COMMIT_USER_FULL, '-q'
                               ])

        rev = self.recipe._freeze_vcs_source('hg', repo_path)
        hg = subprocess.Popen(['hg', '--cwd', repo_path, 'diff', '-r', rev],
                              stdout=subprocess.PIPE,
                              stderr=subprocess.PIPE)
        out, err = hg.communicate()
        if hg.returncode or err:
            self.fail("Invalid extracted revision: %r" % rev)
        self.assertEquals(out, '', 'Extracted revision shows some diff')

    def test_freeze_vcs_source_dirty(self):
        self.make_recipe(version='6.1-1')
        b_dir = self.recipe.buildout_dir
        repo_path = os.path.join(b_dir, 'custom')
        subprocess.check_call(['hg', 'init', repo_path])
        with open(os.path.join(repo_path, 'somefile'), 'w') as f:
            f.write('content')
        subprocess.check_call(['hg', '--cwd', repo_path,
                               'commit', '-A', '-m', 'somerev',
                               '-u', COMMIT_USER_FULL, '-q',
                               ])

        self.recipe.local_modifications = []
        # modification on tracked file
        with open(os.path.join(repo_path, 'somefile'), 'w') as f:
            f.write('changed content')
        self.recipe._freeze_vcs_source('hg', repo_path)
        self.assertTrue(bool(self.recipe.local_modifications))

        subprocess.check_call(['hg', '-q',
                               '--cwd', repo_path, 'revert', '--all'])

        # untracked file
        self.recipe.local_modifications = []
        with open(os.path.join(repo_path, 'untracked'), 'w') as f:
            f.write('something else')
        self.recipe._freeze_vcs_source('hg', repo_path)
        self.assertTrue(bool(self.recipe.local_modifications))

    def test_prepare_frozen_buildout(self):
        self.make_recipe(version='6.1-1')
        conf = ConfigParser()
        self.recipe._prepare_frozen_buildout(conf)
        self.assertTrue('buildout' in conf.sections())

    def test_prepare_frozen_buildout_gp_vcsdevelop(self):
        self.make_recipe(version='6.1-1')
        self.recipe.b_options[GP_VCS_EXTEND_DEVELOP] = (
            "fakevcs+http://example.com/aeroolib#egg=aeroolib")

        conf = ConfigParser()
        self.recipe._prepare_frozen_buildout(conf)
        extends_develop = conf.get('buildout', GP_VCS_EXTEND_DEVELOP)
        self.assertEquals(extends_develop.strip(),
                          "fakevcs+http://example.com/aeroolib@fakerev"
                          "#egg=aeroolib")

    def test_prepare_frozen_buildout_gp_vcsdevelop_already_fixed(self):
        """Test that prepare_frozen_buildout understands existing pinning.

        One might say that we souldn't touch an existing revision pinning, but
        a difference can arise from a tag resolution, or simply someone
        manually updating the repo. In all cases, the instrospected revision
        will be used.
        """
        self.make_recipe(version='6.1-1')
        self.recipe.b_options[GP_VCS_EXTEND_DEVELOP] = (
            "fakevcs+http://example.com/aeroolib@somerev#egg=aeroolib")

        conf = ConfigParser()
        self.recipe._prepare_frozen_buildout(conf)
        extends_develop = conf.get('buildout', GP_VCS_EXTEND_DEVELOP)
        self.assertEquals(extends_develop.strip(),
                          "fakevcs+http://example.com/aeroolib@fakerev"
                          "#egg=aeroolib")
