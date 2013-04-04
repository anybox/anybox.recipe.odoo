"""Test VCS methods.

These tests depend on system executables, such as 'hg', 'bzr', etc.
"""

import unittest
import os
import shutil
import tempfile
import subprocess
from ConfigParser import ConfigParser

from .. import vcs
from ..vcs import HgRepo, BzrBranch, GitRepo, SvnCheckout
from ..vcs import UpdateError
from ..testing import COMMIT_USER_FULL, COMMIT_USER_EMAIL, COMMIT_USER_NAME


class VcsTestCase(unittest.TestCase):
    """Common fixture"""

    def setUp(self):
        sandbox = self.sandbox = tempfile.mkdtemp('test_oerp_recipe_vcs')
        src = self.src_dir = os.path.join(sandbox, 'src')
        dst = self.dst_dir = os.path.join(sandbox, 'dest')
        os.mkdir(src)
        os.mkdir(dst)
        self.create_src()

    def create_src(self):
        """Create a source repository to run most tests.

        To be implemented in subclasses."""
        raise NotImplementedError

    def tearDown(self):
        print "TEARDOWN remove " + self.sandbox
        shutil.rmtree(self.sandbox)


class CommonTestCase(VcsTestCase):
    """Test methods that are common among the different repository classes."""

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
        subprocess.call(['hg', 'commit', '-m', 'initial commit',
                         '-u', COMMIT_USER_FULL])

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
        subprocess.call(['hg', 'commit', '-A', '-m', 'initial commit',
                         '-u', COMMIT_USER_FULL])
        subprocess.call(['hg', 'branch', 'future'])
        f = open('tracked', 'w')
        f.write("future" + os.linesep)
        f.close()
        subprocess.call(['hg', 'commit', '-m', 'in branch',
                         '-u', COMMIT_USER_FULL])

    def assertFutureBranch(self, target_dir):
        """Check that we are on the 'future' branch in target_dir repo."""
        self.assertTrue(os.path.isdir(target_dir))
        f = open(os.path.join(target_dir, 'tracked'))
        lines = f.readlines()
        f.close()
        self.assertEquals(lines[0].strip(), 'future')

    def assertRevision(self, branch, revno):
        p = subprocess.Popen(['hg', '--cwd', branch.target_dir,
                              'parents', '--template={rev}\n'],
                             stdout=subprocess.PIPE)
        self.assertEquals(p.communicate()[0].split(), [str(revno)])

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
        self.assertFutureBranch(target_dir)

    def test_update(self):
        target_dir = os.path.join(self.dst_dir, "clone to update")
        branch = HgRepo(target_dir, self.src_repo)
        branch('default')
        default_heads = branch.parents()

        branch = HgRepo(target_dir, self.src_repo)
        branch('future')
        self.assertFutureBranch(target_dir)
        self.assertNotEqual(branch.parents(), default_heads)

    def test_update_same_branch(self):
        """Test that updating on a revision that we have but is a branch works.

        This should trigger a pull
        """
        target_dir = os.path.join(self.dst_dir, "clone to update")
        branch = HgRepo(target_dir, self.src_repo)
        branch('future')

        self.assertFutureBranch(self.src_repo)
        newfile = os.path.join(self.src_repo, 'newfile')
        with open(newfile, 'w') as f:
            f.write('something')
        subprocess.check_call(['hg', 'commit', '-A', '-m',
                               "new commit on future branch",
                               '-u', COMMIT_USER_FULL])

        branch('future')
        self.assertRevision(branch, 2)  # would not have worked without a pull

    def test_update_fixed_rev(self):
        """Test update on a fixed rev that we already have."""
        target_dir = os.path.join(self.dst_dir, "clone to update")
        branch = HgRepo(target_dir, self.src_repo)
        branch('default')

        branch = HgRepo(target_dir, self.src_repo)
        branch('0')
        self.assertRevision(branch, 0)

    def test_update_missing_fixed_rev(self):
        """Test update on a fixed rev that we don't have."""
        target_dir = os.path.join(self.dst_dir, "clone to update")
        branch = HgRepo(target_dir, self.src_repo)
        branch('default')

        branch = HgRepo(target_dir, self.src_repo)
        branch('future')
        self.assertRevision(branch, 1)

    def test_offline_update_fixed_rev(self):
        """In offline mode, test update on a fixed rev that we already have."""
        target_dir = os.path.join(self.dst_dir, "clone to update")
        branch = HgRepo(target_dir, self.src_repo)
        branch('default')

        branch = HgRepo(target_dir, self.src_repo, offline=True)
        branch('0')
        self.assertRevision(branch, 0)

    def test_offline_update_missing_fixed_rev(self):
        """In offline mode, test update on a fixed rev that we don't have."""
        target_dir = os.path.join(self.dst_dir, "clone to update")
        branch = HgRepo(target_dir, self.src_repo)
        branch('default')

        branch = HgRepo(target_dir, self.src_repo, offline=True)
        self.assertRaises(UpdateError, branch, 'future')

    def test_hgrc_paths_update(self):
        """Method to update hgrc paths updates them and stores old values"""
        target_dir = os.path.join(self.dst_dir, "clone to update")
        repo = HgRepo(target_dir, self.src_repo)
        # initial cloning
        repo('default')

        # first rename
        new_src = os.path.join(self.src_dir, 'new-src-repo')
        HgRepo(target_dir, new_src).update_hgrc_paths()
        parser = ConfigParser()
        parser.read(os.path.join(target_dir, '.hg', 'hgrc'))
        self.assertEquals(parser.get('paths', 'default'), new_src)
        self.assertEquals(parser.get('paths', 'buildout_save_1'),
                          self.src_repo)

        # second rename
        new_src_2 = os.path.join(self.src_dir, 'renew-src-repo')
        HgRepo(target_dir, new_src_2).update_hgrc_paths()
        parser = ConfigParser()
        parser.read(os.path.join(target_dir, '.hg', 'hgrc'))
        self.assertEquals(parser.get('paths', 'default'), new_src_2)
        self.assertEquals(parser.get('paths', 'buildout_save_1'),
                          self.src_repo)
        self.assertEquals(parser.get('paths', 'buildout_save_2'), new_src)

    def test_url_change(self):
        """HgRepo adapts itself to changes in source URL."""
        target_dir = os.path.join(self.dst_dir, "clone to update")
        repo = HgRepo(target_dir, self.src_repo)
        # initial cloning
        repo('default')

        # rename and update
        new_src = os.path.join(self.src_dir, 'new-src-repo')
        os.rename(self.src_repo, new_src)
        HgRepo(target_dir, new_src)('future')
        self.assertFutureBranch(target_dir)

    def test_uncommitted_changes(self):
        """HgRepo can detect uncommitted changes."""
        # initial cloning
        target_dir = os.path.join(self.dst_dir, "clone to update")
        repo = HgRepo(target_dir, self.src_repo)
        repo('default')

        self.assertFalse(repo.uncommitted_changes())

        f = open(os.path.join(target_dir, 'tracked'), 'w')
        f.write('mod')
        f.close()

        self.assertTrue(repo.uncommitted_changes())

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
        subprocess.call(['bzr', 'whoami', '--branch', COMMIT_USER_FULL])
        f = open('tracked', 'w')
        f.write("first" + os.linesep)
        f.close()
        subprocess.call(['bzr', 'add'])
        subprocess.call(['bzr', 'commit', '-m', 'initial commit'])
        f = open('tracked', 'w')
        f.write("last" + os.linesep)
        f.close()
        subprocess.call(['bzr', 'commit', '-m', 'last version'])

    def assertRevision(self, branch, rev, first_line):
        """Assert that branch is at prescribed revision

        Double check with expected first line of 'tracked' file."""
        target_dir = branch.target_dir
        self.assertTrue(os.path.isdir(target_dir))
        f = open(os.path.join(target_dir, 'tracked'))
        lines = f.readlines()
        f.close()
        self.assertEquals(lines[0].strip(), first_line)
        self.assertEquals(branch.parents(), [rev])

    def assertRevision1(self, branch):
        """Assert that branch is at revision 1."""
        self.assertRevision(branch, '1', 'first')

    def assertRevision2(self, branch):
        """Assert that branch is at revision 2."""
        self.assertRevision(branch, '2', 'last')

    def test_branch(self):
        target_dir = os.path.join(self.dst_dir, "My branch")
        branch = BzrBranch(target_dir, self.src_repo)
        branch('last:1')
        self.assertRevision2(branch)

    def test_branch_stacked(self):
        target_dir = os.path.join(self.dst_dir, "My branch")
        branch = BzrBranch(target_dir, self.src_repo,
                           **{'bzr-stacked-branches': 'True'})
        branch('last:1')
        self.assertRevision2(branch)

    def test_branch_to_rev(self):
        """Directly clone and update to given revision."""
        target_dir = os.path.join(self.dst_dir, "My branch")
        branch = BzrBranch(target_dir, self.src_repo)
        branch('1')
        self.assertRevision1(branch)

    def test_update(self):
        """Update to a revision that's not the latest available in target"""
        target_dir = os.path.join(self.dst_dir, "clone to update")
        branch = BzrBranch(target_dir, self.src_repo)('last:1')

        # Testing starts here
        branch = BzrBranch(target_dir, self.src_repo)
        branch('1')
        self.assertRevision1(branch)

    def test_update_offline(self):
        """In offline mode, update to a revision that's already there."""
        target_dir = os.path.join(self.dst_dir, "clone to update")
        branch = BzrBranch(target_dir, self.src_repo)('last:1')

        # Testing starts here
        branch = BzrBranch(target_dir, self.src_repo, offline=True)
        branch('1')
        self.assertRevision1(branch)

    def test_update_needs_pull(self):
        """Update to a revision that needs to be pulled from target."""
        target_dir = os.path.join(self.dst_dir, "clone to update")
        branch = BzrBranch(target_dir, self.src_repo)('1')

        # Testing starts here
        branch = BzrBranch(target_dir, self.src_repo)
        branch('2')
        self.assertRevision2(branch)

    def test_update_needs_pull_offline(self):
        """In offline mode, update to a revision that needs to be pulled."""
        target_dir = os.path.join(self.dst_dir, "clone to update")
        branch = BzrBranch(target_dir, self.src_repo)('1')

        # Testing starts here
        branch = BzrBranch(target_dir, self.src_repo, offline=True)
        self.assertRaises(UpdateError, branch, '2')

    def test_archive(self):
        target_dir = os.path.join(self.dst_dir, "clone to archive")
        branch = BzrBranch(target_dir, self.src_repo)
        branch('1')

        archive_dir = os.path.join(self.dst_dir, "archive directory")
        branch.archive(archive_dir)
        with open(os.path.join(archive_dir, 'tracked')) as f:
            self.assertEquals(f.readlines()[0].strip(), 'first')

    def test_url_update(self):
        """Method to update branch.conf does it and stores old values"""
        # Setting up a prior branch
        target_dir = os.path.join(self.dst_dir, "clone to update")
        branch = BzrBranch(target_dir, self.src_repo)
        branch('1')
        # src may have become relative, let's keep it in that form
        old_src = branch.parse_conf()['parent_location']

        # first rename.
        # We test that pull actually works rather than
        # just checking branch.conf to avoid logical loop testing nothing
        new_src = os.path.join(self.src_dir, 'new-src-repo')
        os.rename(self.src_repo, new_src)
        branch = BzrBranch(target_dir, new_src)
        branch('last:1')

        self.assertEquals(branch.parse_conf(), dict(
            buildout_save_parent_location_1=old_src,
            parent_location=new_src))

        # second rename
        new_src2 = os.path.join(self.src_dir, 'new-src-repo2')
        os.rename(new_src, new_src2)
        branch = BzrBranch(target_dir, new_src2)
        branch('1')

        self.assertEquals(branch.parse_conf(), dict(
            buildout_save_parent_location_1=old_src,
            buildout_save_parent_location_2=new_src,
            parent_location=new_src2))

    def test_url_update_1133248(self):
        """Method to update branch.conf is resilient wrt to actual content.

        See lp:1133248 for details
        """
        # Setting up a prior branch
        target_dir = os.path.join(self.dst_dir, "clone to update")
        branch = BzrBranch(target_dir, self.src_repo)
        branch('1')

        conf_path = os.path.join(target_dir, '.bzr', 'branch', 'branch.conf')
        with open(conf_path, 'a') as conf:
            conf.seek(0, os.SEEK_END)
            conf.write(os.linesep + "Some other stuff" + os.linesep)

        # src may have become relative, let's keep it in that form
        old_src = branch.parse_conf()['parent_location']

        # first rename.
        # We test that pull actually works rather than
        # just checking branch.conf to avoid logical loop testing nothing
        new_src = os.path.join(self.src_dir, 'new-src-repo')
        os.rename(self.src_repo, new_src)
        branch = BzrBranch(target_dir, new_src)
        branch('last:1')

        self.assertEquals(branch.parse_conf(), dict(
            buildout_save_parent_location_1=old_src,
            parent_location=new_src))

    def test_lp_url(self):
        """lp: locations are being rewritten to the actual target."""
        branch = BzrBranch('', 'lp:anybox.recipe.openerp')
        # just testing for now that it's been rewritten
        self.failIf(branch.url.startswith('lp:'))

        # checking idempotency of rewritting
        branch2 = BzrBranch('', branch.url)
        self.assertEquals(branch2.url, branch.url)

    def test_lp_url_nobzrlib(self):
        """We can't safely handle lp: locations without bzrlib."""
        from anybox.recipe.openerp import vcs
        save = vcs.LPDIR
        vcs.LPDIR = None
        self.assertRaises(RuntimeError, BzrBranch, '', 'lp:something')
        vcs.LPDIR = save

    def test_update_clear_locks(self):
        """Testing update with clear locks option."""
        # Setting up a prior branch
        target_dir = os.path.join(self.dst_dir, "clone to update")
        BzrBranch(target_dir, self.src_repo)('last:1')

        # Testing starts here
        branch = BzrBranch(target_dir, self.src_repo, clear_locks=True)
        branch('1')
        self.assertRevision1(branch)

    def test_failed(self):
        target_dir = os.path.join(self.dst_dir, "My branch")
        branch = BzrBranch(target_dir, '/does-not-exist')
        self.assertRaises(subprocess.CalledProcessError,
                          branch.get_update, 'default')


class GitTestCase(VcsTestCase):

    def create_src(self):
        os.chdir(self.src_dir)
        subprocess.call(['git', 'init', 'src-branch'])
        self.src_repo = os.path.join(self.src_dir, 'src-branch')
        os.chdir(self.src_repo)
        # repo configuration is local by default
        subprocess.call(['git', 'config', 'user.email', COMMIT_USER_EMAIL])
        subprocess.call(['git', 'config', 'user.name', COMMIT_USER_NAME])
        f = open('tracked', 'w')
        f.write("first" + os.linesep)
        f.close()
        subprocess.call(['git', 'add', 'tracked'])
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
