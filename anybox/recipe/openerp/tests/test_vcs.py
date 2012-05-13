"""Test VCS methods.

These tests depend on system executables, such as 'hg', 'bzr', etc.
"""

import unittest
import os
import shutil
import tempfile
import subprocess

from anybox.recipe.openerp import vcs

class VcsTestCase(unittest.TestCase):
    """Common fixture."""

    def setUp(self):
        sandbox = self.sandbox = tempfile.mkdtemp('test_oerp_recipe_vcs')
        src = self.src_dir = os.path.join(sandbox, 'src')
        dst = self.dst_dir = os.path.join(sandbox, 'dest')
        os.mkdir(src)
        os.mkdir(dst)
        self.create_src()

    def tearDown(self):
        print "TEARDOWN remove " + self.sandbox
        shutil.rmtree(self.sandbox)

class HgTestCase(VcsTestCase):

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
        vcs.hg_get_update(target_dir, self.src_repo, 'default')
        self.assertTrue(os.path.isdir(target_dir))
        f = open(os.path.join(target_dir, 'tracked'))
        lines = f.readlines()
        f.close()
        self.assertEquals(lines[0].strip(), 'default')

    def test_clone_to_rev(self):
        """Directly clone and update to given revision."""
        target_dir = os.path.join(self.dst_dir, "My clone")
        vcs.hg_get_update(target_dir, self.src_repo, 'future')
        self.assertTrue(os.path.isdir(target_dir))
        f = open(os.path.join(target_dir, 'tracked'))
        lines = f.readlines()
        f.close()
        self.assertEquals(lines[0].strip(), 'future')

    def test_update(self):
        target_dir = os.path.join(self.dst_dir, "clone to update")
        vcs.hg_get_update(target_dir, self.src_repo, 'default')
        vcs.hg_get_update(target_dir, self.src_repo, 'future')
        self.assertTrue(os.path.isdir(target_dir))
        f = open(os.path.join(target_dir, 'tracked'))
        lines = f.readlines()
        f.close()
        self.assertEquals(lines[0].strip(), 'future')

    def test_failed(self):
        target_dir = os.path.join(self.dst_dir, "My clone")
        self.assertRaises(subprocess.CalledProcessError, vcs.hg_get_update,
                          target_dir, '/does-not-exist', 'default')

class BzrTestCase(VcsTestCase):

    def create_src(self):
        os.chdir(self.src_dir)
        subprocess.call(['bzr', 'init', 'src-branch'])
        self.src_repo = os.path.join(self.src_dir, 'src-branch')
        os.chdir(self.src_repo)
        subprocess.call(['bzr', '--branch', 'whoami',
                         'Joe Test <joe@test.example>'])
        f = open('tracked', 'w')
        f.write("first" + os.linesep)
        f.close()
        subprocess.call(['bzr', 'add'])
        subprocess.call(['bzr', 'commit', '-m', 'initial commit'])
        f = open('tracked', 'w')
        f.write("last" + os.linesep)
        f.close()
        subprocess.call(['bzr', 'commit', '-m', 'last version'])

    def test_branch(self):
        target_dir = os.path.join(self.dst_dir, "My branch")
        vcs.bzr_get_update(target_dir, self.src_repo, 'last:1')
        self.assertTrue(os.path.isdir(target_dir))
        f = open(os.path.join(target_dir, 'tracked'))
        lines = f.readlines()
        f.close()
        self.assertEquals(lines[0].strip(), 'last')

    def test_branch_to_rev(self):
        """Directly clone and update to given revision."""
        target_dir = os.path.join(self.dst_dir, "My branch")
        vcs.bzr_get_update(target_dir, self.src_repo, '1')
        self.assertTrue(os.path.isdir(target_dir))
        f = open(os.path.join(target_dir, 'tracked'))
        lines = f.readlines()
        f.close()
        self.assertEquals(lines[0].strip(), 'first')

    def test_update(self):
        # Setting up a prior branch
        target_dir = os.path.join(self.dst_dir, "clone to update")
        vcs.bzr_get_update(target_dir, self.src_repo, 'last:1')

        # Testing starts here
        vcs.bzr_get_update(target_dir, self.src_repo, '1')
        self.assertTrue(os.path.isdir(target_dir))
        f = open(os.path.join(target_dir, 'tracked'))
        lines = f.readlines()
        f.close()
        self.assertEquals(lines[0].strip(), 'first')

    def test_update_clear_locks(self):
        """Testing update with clear locks option."""
        # Setting up a prior branch
        target_dir = os.path.join(self.dst_dir, "clone to update")
        vcs.bzr_get_update(target_dir, self.src_repo, 'last:1')

        # Testing starts here
        vcs.bzr_get_update(target_dir, self.src_repo, '1', clear_locks=True)
        self.assertTrue(os.path.isdir(target_dir))
        f = open(os.path.join(target_dir, 'tracked'))
        lines = f.readlines()
        f.close()
        self.assertEquals(lines[0].strip(), 'first')

    def test_failed(self):
        target_dir = os.path.join(self.dst_dir, "My branch")
        self.assertRaises(subprocess.CalledProcessError, vcs.bzr_get_update,
                          target_dir, '/does-not-exist', 'default')

