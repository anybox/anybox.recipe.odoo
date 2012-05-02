"""Test the server recipe.

NB: zc.buildout.testing provides utilities for integration tests, with
an embedded http server, etc.
"""
import unittest

import os
import shutil
from tempfile import mkdtemp
from anybox.recipe.openerp import ServerRecipe

class TestServer(unittest.TestCase):

    def setUp(self):
        b_dir = self.buildout_dir = mkdtemp('test_oerp_recipe')
        self.buildout = {}
        self.buildout['buildout'] = {
            'directory': b_dir,
            'offline': False,
            'parts-directory': os.path.join(b_dir, 'parts'),
            'bin-directory': os.path.join(b_dir, 'bin'),
            }

    def make_recipe(self, name='openerp', **options):
        self.recipe = ServerRecipe(self.buildout, name, options)

    def tearDown(self):
        shutil.rmtree(self.buildout_dir)

    def test_correct_v_6_1(self):
        self.make_recipe(version='6.1')
        self.assertEquals(self.recipe.version_wanted, '6.1-1')
