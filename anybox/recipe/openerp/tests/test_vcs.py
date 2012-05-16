"""Test VCS methods.

These tests depend on system executables, such as 'hg', 'bzr', etc.
"""

import unittest
import os
import shutil
import tempfile
import subprocess

from anybox.recipe.openerp import vcs
from anybox.recipe.openerp.vcs import HgRepo, BzrBranch, GitRepo, SvnCheckout

class VcsTestCase(unittest.TestCase):
    """Common fixture"""

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

class CommonTestCase(VcsTestCase):

    def create_src(self):
        """We use HgRepo to test the common features."""

        os.chdir(self.src_dir)
        subprocess.call(['hg', 'init', 'src-repo'])
        self.src_repo = os.path.join(self.src_dir, 'src-repo')
        os.chdir('src-repo')
        f = open('tracked', 'w')
        f.write("default" + os.linesep)
        f.close()
        subprocess.call(['hg', 'add'])
        subprocess.call(['hg', 'commit', '-m', 'initial commit'])

    def test_unknown(self):
        self.assertRaises(ValueError,
                          vcs.get_update, 'unknown', '', '', 'default')

    def test_retry(self):
        """With a repo class that fails updates, retry works."""

        class HgRepoFailsUpdates(HgRepo):
            def get_update(self, revision):
                if os.path.exists(self.target_dir):
                    raise vcs.UpdateError(1, ['error'])
                HgRepo.get_update(self, revision)

        vcs.SUPPORTED['hg_fails_updates'] = HgRepoFailsUpdates
        repo_path = os.path.join(self.dst_dir, "clone")

        vcs.get_update('hg_fails_updates', repo_path, self.src_repo, 'default')
        self.assertTrue(os.path.isdir(repo_path))

        # without the retry option
        self.assertRaises(vcs.UpdateError, vcs.get_update, 'hg_fails_updates',
                          repo_path, self.src_repo, 'default')

        # now the retry
        vcs.get_update('hg_fails_updates', repo_path, self.src_repo, 'default',
                       clear_retry=True)

        # no such wild retry in offline mode
        self.assertRaises(vcs.UpdateError, vcs.get_update, 'hg_fails_updates',
                          repo_path, self.src_repo, 'default', offline=True)

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
        HgRepo(target_dir, self.src_repo)('default')

        self.assertTrue(os.path.isdir(target_dir))
        f = open(os.path.join(target_dir, 'tracked'))
        lines = f.readlines()
        f.close()
        self.assertEquals(lines[0].strip(), 'default')

    def test_clone_to_rev(self):
        """Directly clone and update to given revision."""
        target_dir = os.path.join(self.dst_dir, "My clone")
        HgRepo(target_dir, self.src_repo)('future')

        self.assertTrue(os.path.isdir(target_dir))
        f = open(os.path.join(target_dir, 'tracked'))
        lines = f.readlines()
        f.close()
        self.assertEquals(lines[0].strip(), 'future')

    def test_update(self):
        target_dir = os.path.join(self.dst_dir, "clone to update")
        HgRepo(target_dir, self.src_repo)('default')
        HgRepo(target_dir, self.src_repo)('future')
        self.assertTrue(os.path.isdir(target_dir))
        f = open(os.path.join(target_dir, 'tracked'))
        lines = f.readlines()
        f.close()
        self.assertEquals(lines[0].strip(), 'future')

    def test_failed(self):
        target_dir = os.path.join(self.dst_dir, "My clone")
        repo = HgRepo(target_dir, '/does-not-exit')
        self.assertRaises(subprocess.CalledProcessError,
                          repo.get_update, 'default')

class BzrTestCase(VcsTestCase):

    def create_src(self):
        os.chdir(self.src_dir)
        subprocess.call(['bzr', 'init', 'src-branch'])
        self.src_repo = os.path.join(self.src_dir, 'src-branch')
        os.chdir(self.src_repo)
        subprocess.call(['bzr', 'whoami', '--branch',
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
        BzrBranch(target_dir, self.src_repo)('last:1')

        self.assertTrue(os.path.isdir(target_dir))
        f = open(os.path.join(target_dir, 'tracked'))
        lines = f.readlines()
        f.close()
        self.assertEquals(lines[0].strip(), 'last')

    def test_branch_to_rev(self):
        """Directly clone and update to given revision."""
        target_dir = os.path.join(self.dst_dir, "My branch")
        BzrBranch(target_dir, self.src_repo)('1')
        self.assertTrue(os.path.isdir(target_dir))
        f = open(os.path.join(target_dir, 'tracked'))
        lines = f.readlines()
        f.close()
        self.assertEquals(lines[0].strip(), 'first')

    def test_update(self):
        # Setting up a prior branch
        target_dir = os.path.join(self.dst_dir, "clone to update")
        BzrBranch(target_dir, self.src_repo)('last:1')

        # Testing starts here
        BzrBranch(target_dir, self.src_repo)('1')
        self.assertTrue(os.path.isdir(target_dir))
        f = open(os.path.join(target_dir, 'tracked'))
        lines = f.readlines()
        f.close()
        self.assertEquals(lines[0].strip(), 'first')

    def test_update_clear_locks(self):
        """Testing update with clear locks option."""
        # Setting up a prior branch
        target_dir = os.path.join(self.dst_dir, "clone to update")
        BzrBranch(target_dir, self.src_repo)('last:1')

        # Testing starts here
        BzrBranch(target_dir, self.src_repo, clear_locks=True)('1')
        self.assertTrue(os.path.isdir(target_dir))
        f = open(os.path.join(target_dir, 'tracked'))
        lines = f.readlines()
        f.close()
        self.assertEquals(lines[0].strip(), 'first')

    def test_failed(self):
        target_dir = os.path.join(self.dst_dir, "My branch")
        branch = BzrBranch(target_dir, '/does-not-exist')
        self.assertRaises(subprocess.CalledProcessError, branch.get_update,
                          'default')


class GitTestCase(VcsTestCase):

    def create_src(self):
        os.chdir(self.src_dir)
        subprocess.call(['git', 'init', 'src-branch'])
        self.src_repo = os.path.join(self.src_dir, 'src-branch')
        os.chdir(self.src_repo)
        f = open('tracked', 'w')
        f.write("first" + os.linesep)
        f.close()
        subprocess.call(['git', 'add'])
        subprocess.call(['git', 'commit', '-m', 'initial commit'])
        f = open('tracked', 'w')
        f.write("last" + os.linesep)
        f.close()
        subprocess.call(['git', 'add', 'tracked'])
        subprocess.call(['git', 'commit', '-m', 'last version'])

    def test_clone(self):
        """Git clone."""
        target_dir = os.path.join(self.dst_dir, "My clone")
        GitRepo(target_dir, self.src_repo)('master')

        self.assertTrue(os.path.isdir(target_dir))
        f = open(os.path.join(target_dir, 'tracked'))
        lines = f.readlines()
        f.close()
        self.assertEquals(lines[0].strip(), 'last')


class SvnTestCase(VcsTestCase):

    def create_src(self):
        os.chdir(self.src_dir)
        subprocess.check_call(['svnadmin', 'create', 'src-repo'])
        self.src_repo = os.path.join(self.src_dir, 'src-repo')
        self.src_repo = 'file://' + self.src_repo

        tmp_checkout = os.path.join(self.src_dir, 'tmp_checkout')
        subprocess.call(['svn', 'checkout', self.src_repo, tmp_checkout])

        os.chdir(tmp_checkout)
        f = open('tracked', 'w')
        f.write("first" + os.linesep)
        f.close()
        subprocess.call(['svn', 'add', 'tracked'])
        subprocess.call(['svn', 'commit', '-m', 'initial commit'])
        f = open('tracked', 'w')
        f.write("last" + os.linesep)
        f.close()
        subprocess.call(['svn', 'commit', '-m', 'last version'])

    def test_checkout(self):
        """Svn clone."""
        target_dir = os.path.join(self.dst_dir, "Mycheckout")
        SvnCheckout(target_dir, self.src_repo)('head')

        self.assertTrue(os.path.isdir(target_dir))
        f = open(os.path.join(target_dir, 'tracked'))
        lines = f.readlines()
        f.close()
        self.assertEquals(lines[0].strip(), 'last')
