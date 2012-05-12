"""Test VCS methods.

These tests depend on system executables, such as 'hg', 'bzr', etc.
"""

import unittest
import os
import shutil
import tempfile
import subprocess

from anybox.recipe.openerp import ServerRecipe

class VcsTestCase(unittest.TestCase):
    """Common fixture."""

    def setUp(self):
        sandbox = self.sandbox = tempfile.mkdtemp('test_oerp_recipe_vcs')
        src = self.src_dir = os.path.join(sandbox, 'src')
        dst = self.dst_dir = os.path.join(sandbox, 'dest')
        os.mkdir(src)
        os.mkdir(dst)
        self.create_recipe()
        self.create_src()

    def create_recipe(self):
        """Temporary while vcs calls still are Recipe methods."""
        b_dir = self.sandbox
        self.buildout = {}
        self.buildout['buildout'] = {
            'directory': b_dir,
            'offline': False,
            'parts-directory': os.path.join(b_dir, 'parts'),
            'bin-directory': os.path.join(b_dir, 'bin'),
            }
        self.recipe = ServerRecipe(self.buildout, 'vcs-test', dict(version='6.1'))

    def tearDown(self):
        shutil.rmtree(self.sandbox)

class HgTestCase(VcsTestCase):

    def setUp(self):
        super(HgTestCase, self).setUp()
        self.create_src()
        self.create_recipe()

    def create_src(self):
        os.chdir(self.src_dir)
        subprocess.call(['hg', 'init', 'src-repo'])
        self.src_repo = os.path.join(self.src_dir, 'src-repo')
        os.chdir('src-repo')
        f = open('tracked', 'w')
        f.write("default" + os.linesep)
        f.close()
        subprocess.call(['hg', 'add'])
        subprocess.call(['hg', 'commit', '-m', 'initial commit'])
        subprocess.call(['hg', 'branch', 'future'])
        f = open('tracked', 'w')
        f.write("future" + os.linesep)
        f.close()
        subprocess.call(['hg', 'commit', '-m', 'in branch'])

    def test_clone(self):
        target_dir = os.path.join(self.dst_dir, "My clone")
        self.recipe.hg_get_update(target_dir, self.src_repo, 'default')
        self.assertTrue(os.path.isdir(target_dir))
        f = open(os.path.join(target_dir, 'tracked'))
        lines = f.readlines()
        f.close()
        self.assertEquals(lines[0].strip(), 'default')

    def test_clone_to_rev(self):
        """Directly clone and update to given revision."""
        target_dir = os.path.join(self.dst_dir, "My clone")
        self.recipe.hg_get_update(target_dir, self.src_repo, 'future')
        self.assertTrue(os.path.isdir(target_dir))
        f = open(os.path.join(target_dir, 'tracked'))
        lines = f.readlines()
        f.close()
        self.assertEquals(lines[0].strip(), 'future')

    def test_update(self):
        target_dir = os.path.join(self.dst_dir, "clone to update")
        self.recipe.hg_get_update(target_dir, self.src_repo, 'default')
        self.recipe.hg_get_update(target_dir, self.src_repo, 'future')
        self.assertTrue(os.path.isdir(target_dir))
        f = open(os.path.join(target_dir, 'tracked'))
        lines = f.readlines()
        f.close()
        self.assertEquals(lines[0].strip(), 'future')
