import os
import tempfile
import shutil
import subprocess
from ConfigParser import ConfigParser, NoOptionError
from ..base import GP_VCS_EXTEND_DEVELOP
from ..testing import RecipeTestCase
from ..testing import COMMIT_USER_FULL


class TestFreeze(RecipeTestCase):

    test_dir = os.path.dirname(__file__)

    def test_freeze_egg_versions(self):
        """Test that an egg requirement is properly dumped with its version.
        """
        conf = ConfigParser()
        conf.add_section('freeze')
        self.make_recipe(version='10.0')
        self.fill_working_set(fictive=True)
        self.recipe._freeze_egg_versions(conf, 'freeze')
        try:
            version = conf.get('freeze', self.fictive_dist_name)
        except NoOptionError:
            self.fail("Expected version of %s "
                      "egg not dumped !" % self.fictive_dist_name)
        self.assertEqual(version, self.fictive_version)

    def test_freeze_egg_versions_merge(self):
        """Test that freezing of egg versions keeps eggs already dumped.

        very much similar to test_freeze_egg_versions.
        """
        conf = ConfigParser()
        conf.add_section('freeze')
        conf.set('freeze', 'some.distribution', '1.0alpha')
        self.make_recipe(version='10.0')
        self.fill_working_set(fictive=True)
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
        self.make_recipe(version='10.0')
        self.develop_fictive(require_install=True)
        self.recipe._freeze_egg_versions(conf, 'freeze')
        self.assertRaises(NoOptionError, conf.get, 'freeze',
                          self.fictive_dist_name)

    def test_freeze_vcs_source(self):
        self.make_recipe(version='10.0')
        b_dir = self.recipe.buildout_dir
        repo_path = os.path.join(b_dir, 'custom')
        subprocess.check_call(['hg', 'init', repo_path])
        with open(os.path.join(repo_path, 'somefile'), 'w') as f:
            f.write('content')
        subprocess.check_call(['hg', '--cwd', repo_path,
                               'commit', '-A', '-m', 'somerev',
                               '-u', COMMIT_USER_FULL, '-q'
                               ])

        rev = self.recipe._freeze_vcs_source('hg', repo_path, 'default')
        hg = subprocess.Popen(['hg', '--cwd', repo_path, 'diff', '-r', rev],
                              stdout=subprocess.PIPE,
                              stderr=subprocess.PIPE)
        out, err = hg.communicate()
        if hg.returncode or err:
            self.fail("Invalid extracted revision: %r" % rev)
        self.assertEquals(out, '', 'Extracted revision shows some diff')

    def test_freeze_vcs_source_already_frozen(self):
        self.make_recipe(version='10.0')
        b_dir = self.recipe.buildout_dir
        repo_path = os.path.join(b_dir, 'custom')
        subprocess.check_call(['hg', 'init', repo_path])
        with open(os.path.join(repo_path, 'somefile'), 'w') as f:
            f.write('content')
        subprocess.check_call(['hg', '--cwd', repo_path,
                               'commit', '-A', '-m', 'somerev',
                               '-u', COMMIT_USER_FULL, '-q'
                               ])
        subprocess.check_call(['hg', '--cwd', repo_path,
                               'tag', 'sometag',
                               '-u', COMMIT_USER_FULL, '-q'
                               ])

        self.assertEqual(
            self.recipe._freeze_vcs_source('hg', repo_path, 'sometag'),
            'sometag')
        self.assertNotEqual(
            self.recipe._freeze_vcs_source('hg', repo_path, 'default'),
            'default')

    def test_freeze_vcs_source_dirty(self):
        self.make_recipe(version='10.0')
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
        self.recipe._freeze_vcs_source('hg', repo_path, 'default')
        self.assertTrue(bool(self.recipe.local_modifications))

        subprocess.check_call(['hg', '-q',
                               '--cwd', repo_path, 'revert', '--all'])

        # untracked file
        self.recipe.local_modifications = []
        with open(os.path.join(repo_path, 'untracked'), 'w') as f:
            f.write('something else')
        self.recipe._freeze_vcs_source('hg', repo_path, 'default')
        self.assertTrue(bool(self.recipe.local_modifications))

    def test_prepare_frozen_buildout(self):
        self.make_recipe(version='10.0')
        conf = ConfigParser()
        self.recipe._prepare_frozen_buildout(conf)
        self.assertTrue('buildout' in conf.sections())

    def test_prepare_frozen_buildout_gp_vcsdevelop(self):
        self.make_recipe(version='10.0')
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
        self.make_recipe(version='10.0')
        self.recipe.b_options[GP_VCS_EXTEND_DEVELOP] = (
            "fakevcs+http://example.com/aeroolib@somerev#egg=aeroolib")

        conf = ConfigParser()
        self.recipe._prepare_frozen_buildout(conf)
        extends_develop = conf.get('buildout', GP_VCS_EXTEND_DEVELOP)
        self.assertEquals(extends_develop.strip(),
                          "fakevcs+http://example.com/aeroolib@fakerev"
                          "#egg=aeroolib")

    def test_freeze_to(self):
        """Test the whole freeze method."""

        self.make_recipe(
            version='pr_fakevcs http://main.soft.example odooo refspec',
            addons="pr_fakevcs http://repo.example target rev1\n"
            "local somwehere\n"
            "pr_fakevcs http://repo2.example stdln rev2 group=stdl"
        )
        os.mkdir(self.recipe.parts)
        os.mkdir(os.path.join(self.recipe.odoo_dir))
        self.recipe.retrieve_main_software()
        self.recipe.retrieve_addons()
        self.fill_working_set(babel=True)

        tmpdir = tempfile.mkdtemp('test_recipe_freeze')
        frozen_path = os.path.join(tmpdir, 'frozen.cfg')
        outconf = ConfigParser()
        try:
            self.recipe.freeze_to(frozen_path)
            outconf.read(frozen_path)
        finally:
            shutil.rmtree(tmpdir)

        # the key in the addons sources for the standalone one has been
        # shifted, that's just what the group option does internally
        self.assertEqual(outconf.get('odoo', 'revisions').splitlines(),
                         ['refspec', 'target rev1', 'stdl/stdln rev2'])
