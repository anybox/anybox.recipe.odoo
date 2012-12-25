import unittest

import os
import sys
import shutil
from tempfile import mkdtemp
import subprocess
from ConfigParser import ConfigParser, NoOptionError
from anybox.recipe.openerp.server import BaseRecipe
from anybox.recipe.openerp.base import main_software


class TestingRecipe(BaseRecipe):
    """A subclass with just enough few defaults for unit testing."""

    archive_filenames = {'6.1': 'blob-%s.tgz'}
    archive_nightly_filenames = {'6.1': '6-1-nightly-%s.tbz'}

class TestBaseRecipe(unittest.TestCase):

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
        shutil.rmtree(self.buildout_dir)

    def make_recipe(self, name='openerp', **options):
        self.recipe = TestingRecipe(self.buildout, name, options)

    def get_source_type(self):
        return self.recipe.sources[main_software][0]

    def get_source_url(self):
        return self.recipe.sources[main_software][1][0]

    def assertDownloadUrl(self, url):
        """Assert that main software is 'downloadable' with given url."""
        source = self.recipe.sources[main_software]
        self.assertEquals(source[0], 'downloadable')
        self.assertEquals(source[1][0], url)

    def test_version_release_6_1(self):
        self.make_recipe(version='6.1-1')

        recipe = self.recipe
        self.assertEquals(recipe.version_wanted, '6.1-1')
        self.assertDownloadUrl(
            'http://nightly.openerp.com/6.1/releases/blob-6.1-1.tgz')

    def test_version_nightly_6_1(self):
        self.make_recipe(version='nightly 6.1 1234-5')

        self.assertDownloadUrl(
            'http://nightly.openerp.com/6.1/nightly/src/6-1-nightly-1234-5.tbz')

    def test_version_bzr_6_1(self):
        self.make_recipe(
            version='bzr lp:openobject-server/6.1 openerp-6.1 last:1')

        recipe = self.recipe
        self.assertEquals(self.get_source_type(), 'bzr')
        self.assertEquals(self.get_source_url(), 'lp:openobject-server/6.1')
        self.assertEquals(recipe.openerp_dir,
                          os.path.join(recipe.parts, 'openerp-6.1'))

    def test_version_local(self):
        local_path = 'path/to/local/version'
        self.make_recipe(version='local ' + local_path)
        recipe = self.recipe
        self.assertEquals(self.get_source_type(), 'local')
        self.assertTrue(recipe.openerp_dir.endswith(local_path))

    def test_version_url(self):
        url = 'http://download.example/future/openerp-12.0.tgz'
        self.make_recipe(version='url ' + url)
        recipe = self.recipe
        self.assertDownloadUrl(url)
        self.assertEquals(recipe.archive_filename, 'openerp-12.0.tgz')

    def test_base_url(self):
        self.make_recipe(version='6.1-1', base_url='http://example.org/openerp')
        self.assertDownloadUrl('http://example.org/openerp/blob-6.1-1.tgz')

    def test_base_url_nightly(self):
        self.make_recipe(version='nightly 6.1 1234-5',
                         base_url='http://example.org/openerp')
        self.assertDownloadUrl(
                          'http://example.org/openerp/6-1-nightly-1234-5.tbz')

    def test_buildout_cfg_name(self):
        self.make_recipe(version='6.1-1')
        bcn = self.recipe.buildout_cfg_name
        self.assertEquals(bcn(), 'buildout.cfg')
        self.assertEquals(bcn(('-D', 'install', 'openerp')), 'buildout.cfg')
        self.assertEquals(bcn(('-c', '6.1.cfg')), '6.1.cfg')
        self.assertEquals(bcn(('--config', '6.1.cfg')), '6.1.cfg')
        self.assertEquals(bcn(('-o', '--config', '6.1.cfg')), '6.1.cfg')
        self.assertEquals(bcn(('--config=6.1.cfg',)), '6.1.cfg')
        self.assertEquals(bcn(('--config=6.1.cfg', '-o')), '6.1.cfg')

    def test_freeze_egg_versions(self):
        """Test that an egg requirement is properly dumped with its version.

        Since nose is our test launcher, we use it as an example, because it
        must be available without downloading anything."""
        conf = ConfigParser()
        conf.add_section('freeze')
        self.make_recipe(version='6.1-1')
        self.recipe.options['eggs'] = 'nose'
        self.recipe.install_requirements() # to get 'ws' attribute
        self.recipe._freeze_egg_versions(conf, 'freeze')
        try:
            nose_version = conf.get('freeze', 'nose')
        except NoOptionError:
            self.fail("Expected version of nose egg not dumped !")
        import nose
        # GR: maybe that'll turn out to be frail
        self.assertEquals(nose_version, nose.__version__)

    def test_freeze_egg_versions_merge(self):
        """Test that freezing of egg versions keeps eggs already dumped.

        very much similar to test_freeze_egg_versions.
        """
        conf = ConfigParser()
        conf.add_section('freeze')
        conf.set('freeze', 'some.distribution', '1.0alpha')
        self.make_recipe(version='6.1-1')
        self.recipe.options['eggs'] = 'nose'
        self.recipe.install_requirements() # to get 'ws' attribute
        self.recipe._freeze_egg_versions(conf, 'freeze')
        try:
            version = conf.get('freeze', 'some.distribution')
        except NoOptionError:
            self.fail("Expected version of 'some.distribution' not kept !")
        self.assertEquals(version, '1.0alpha')

    def test_freeze_vcs_source(self):
        self.make_recipe(version='6.1-1')
        b_dir = self.recipe.buildout_dir
        repo_path = os.path.join(b_dir, 'custom')
        subprocess.check_call(['hg', 'init', repo_path])
        with open(os.path.join(repo_path, 'somefile'), 'w') as f:
            f.write('content')
        subprocess.check_call(['hg', '--cwd', repo_path,
                               'commit', '-A', '-m', 'somerev'])

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
                               'commit', '-A', '-m', 'somerev'])

        # modification on tracked file
        with open(os.path.join(repo_path, 'somefile'), 'w') as f:
            f.write('changed content')
        self.assertRaises(RuntimeError,
                          self.recipe._freeze_vcs_source, 'hg', repo_path)
        subprocess.check_call(['hg', '--cwd', repo_path, 'revert', '--all'])

        # untracked file
        with open(os.path.join(repo_path, 'untracked'), 'w') as f:
            f.write('something else')
        self.assertRaises(RuntimeError,
                          self.recipe._freeze_vcs_source, 'hg', repo_path)
