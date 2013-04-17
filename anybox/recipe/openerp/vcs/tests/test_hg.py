"""VCS tests: Mercurial."""

import os
import subprocess
from ConfigParser import ConfigParser
from ..testing import COMMIT_USER_FULL
from ..testing import VcsTestCase
from ..hg import HgRepo
from ..base import UpdateError


class HgBaseTestCase(VcsTestCase):
    """Common utilities for Mercurial test cases."""

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

    def make_clone(self, path, initial_rev):
        """Make a clone of the source at initial_rev.
        """
        target_dir = os.path.join(self.dst_dir, initial_rev)
        repo = HgRepo(target_dir, self.src_repo)
        repo(initial_rev)
        return repo

    def assertFutureBranch(self, repo):
        """Check that we are on the 'future' branch in target_dir repo."""
        target_dir = repo.target_dir
        self.assertTrue(os.path.isdir(target_dir))
        f = open(os.path.join(target_dir, 'tracked'))
        lines = f.readlines()
        f.close()
        self.assertEquals(lines[0].strip(), 'future')

    def assertDefaultBranch(self, repo):
        """Check that we are on the 'future' branch in target_dir repo."""
        target_dir = repo.target_dir
        self.assertTrue(os.path.isdir(target_dir))
        f = open(os.path.join(target_dir, 'tracked'))
        lines = f.readlines()
        f.close()
        self.assertEquals(lines[0].strip(), 'default')

    def assertRevision(self, branch, revno):
        p = subprocess.Popen(['hg', '--cwd', branch.target_dir,
                              'parents', '--template={rev}\n'],
                             stdout=subprocess.PIPE)
        self.assertEquals(p.communicate()[0].split(), [str(revno)])


class HgTestCase(HgBaseTestCase):

    def test_clone(self):
        repo = self.make_clone("My clone", 'default')
        self.assertDefaultBranch(repo)

    def test_clone_to_rev(self):
        """Directly clone and update to given revision."""
        repo = self.make_clone("My clone", 'future')
        self.assertFutureBranch(repo)

    def test_update(self):
        repo = self.make_clone("clone to update", 'default')
        default_heads = repo.parents()

        repo('future')
        self.assertFutureBranch(repo)
        self.assertNotEqual(repo.parents(), default_heads)

    def test_update_same_branch(self):
        """Test that updating on a revision that we have but is a branch works.

        This should trigger a pull
        """
        repo = self.make_clone("clone to update", 'future')

        # let's make a new revision in the remote repo
        newfile = os.path.join(self.src_repo, 'newfile')
        with open(newfile, 'w') as f:
            f.write('something')
        subprocess.check_call(['hg', '--cwd', self.src_repo,
                               'commit', '-A', '-m',
                               "new commit on future branch",
                               '-u', COMMIT_USER_FULL])

        repo('future')
        self.assertFutureBranch(repo)
        self.assertRevision(repo, 2)  # would not have worked without a pull

    def test_update_fixed_rev(self):
        """Test update on a fixed rev that we already have."""
        repo = self.make_clone("clone to update", 'default')
        repo('0')
        self.assertRevision(repo, 0)

    def test_update_missing_fixed_rev(self):
        """Test update on a fixed rev that we don't have."""
        repo = self.make_clone("clone to update", 'default')
        repo('1')
        self.assertRevision(repo, 1)

    def test_hgrc_paths_update(self):
        """Method to update hgrc paths updates them and stores old values"""
        repo = self.make_clone("clone to update", 'default')
        target_dir = repo.target_dir

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
        repo = self.make_clone("clone to update", 'default')
        target_dir = repo.target_dir

        # rename and update
        new_src = os.path.join(self.src_dir, 'new-src-repo')
        os.rename(self.src_repo, new_src)
        repo = HgRepo(target_dir, new_src)
        repo('future')
        self.assertFutureBranch(repo)

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


class HgOfflineTestCase(HgBaseTestCase):

    def make_clone(self, path, initial_rev):
        """Make a local branch of the source at initial_rev and forbid pulls.
        """
        repo = HgBaseTestCase.make_clone(self, path, initial_rev)
        repo.offline = True

        def _pull():
            raise UpdateError("Should not pull !")
        repo._pull = _pull
        return repo

    def test_update_fixed_rev(self):
        """[offline mode] test update on a fixed rev that we already have."""
        repo = self.make_clone("clone to update", 'default')
        repo('0')
        self.assertRevision(repo, 0)

    def test_update_missing_fixed_rev(self):
        """[offline mode] update on a fixed rev that we don't have raises."""
        repo = self.make_clone("clone to update", 'default')
        self.assertRaises(UpdateError, repo, 'future')

    def test_update_branch_head(self):
        """[offline mode] update on branch head should not pull"""
        repo = self.make_clone("clone to update", '0')
        repo('default')
        self.assertRevision(repo, '0')
