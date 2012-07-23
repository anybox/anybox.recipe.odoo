import unittest

import os
import shutil
from tempfile import mkdtemp
from anybox.recipe.openerp.server import BaseRecipe

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

    def test_parse_version(self):
        pass
