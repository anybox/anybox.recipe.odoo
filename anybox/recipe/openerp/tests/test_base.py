import unittest

import os
import shutil
from tempfile import mkdtemp
from anybox.recipe.openerp.server import BaseRecipe


class TestingRecipe(BaseRecipe):
    """A subclass with just enough few defaults for unit testing."""

    archive_filenames = {'6.1': '6-1-blob-%s'}
    archive_nightly_filenames = {'6.1': '6-1-nightly-%s'}

class TestBaseRecipe(unittest.TestCase):

    def setUp(self):
        b_dir = self.buildout_dir = mkdtemp('test_oerp_base_recipe')
        self.buildout = {}
        self.buildout['buildout'] = {
            'directory': b_dir,
            'offline': False,
            'parts-directory': os.path.join(b_dir, 'parts'),
            'bin-directory': os.path.join(b_dir, 'bin'),
            }

    def tearDown(self):
        shutil.rmtree(self.buildout_dir)

    def make_recipe(self, name='openerp', **options):
        recipe = self.recipe = TestingRecipe(self.buildout, name, options)

    def test_version_release_6_1(self):
        self.make_recipe(version='6.1-1')

        recipe = self.recipe
        self.assertEquals(recipe.version_wanted, '6.1-1')
        self.assertEquals(recipe.type, 'downloadable')
        self.assertEquals(
            recipe.url,
            'http://nightly.openerp.com/6.1/releases/6-1-blob-6.1-1')

    def test_version_nightly_6_1(self):
        self.make_recipe(version='nightly 6.1 1234-5')

        recipe = self.recipe
        self.assertEquals(recipe.type, 'downloadable')
        self.assertEquals(
            recipe.url,
            'http://nightly.openerp.com/6.1/nightly/src/6-1-nightly-1234-5')

    def test_version_bzr_6_1(self):
        self.make_recipe(
            version='bzr lp:openobject-server/6.1 openerp-6.1 last:1')

        recipe = self.recipe
        self.assertEquals(recipe.type, 'bzr')
        self.assertEquals(recipe.url, 'lp:openobject-server/6.1')
        self.assertEquals(recipe.openerp_dir,
                          os.path.join(recipe.parts, 'openerp-6.1'))

    def test_version_local(self):
        local_path = 'path/to/local/version'
        self.make_recipe(version='local ' + local_path)
        recipe = self.recipe
        self.assertEquals(recipe.type, 'local')
        self.assertTrue(recipe.openerp_dir.endswith(local_path))

