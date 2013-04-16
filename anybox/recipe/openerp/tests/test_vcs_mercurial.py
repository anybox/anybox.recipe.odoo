"""VCS tests: Mercurial."""

import os
import subprocess
from ConfigParser import ConfigParser
from ..testing import COMMIT_USER_FULL
from ..testing import VcsTestCase
from ..vcs import HgRepo
from ..vcs import UpdateError


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

    def test_offline_update_branch_head(self):
        """In offline mode, test update on a fixed rev that we already have."""
        target_dir = os.path.join(self.dst_dir, "clone to update")
        branch = HgRepo(target_dir, self.src_repo)
        branch('0')

        branch = HgRepo(target_dir, self.src_repo, offline=True)
        branch('default')
        self.assertRevision(branch, '0')

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
