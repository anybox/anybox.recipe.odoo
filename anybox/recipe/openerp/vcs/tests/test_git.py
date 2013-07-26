"""VCS tests: Git."""

import os
import subprocess
from ..testing import COMMIT_USER_EMAIL
from ..testing import COMMIT_USER_NAME
from ..testing import VcsTestCase
from ..git import GitRepo
from ...utils import working_directory_keeper


class GitBaseTestCase(VcsTestCase):
    """Common utilities for Git test cases."""

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


class GitTestCase(GitBaseTestCase):

    def test_clone(self):
        """Git clone."""
        target_dir = os.path.join(self.dst_dir, "My clone")
        GitRepo(target_dir, self.src_repo)('master')

        self.assertTrue(os.path.isdir(target_dir))
        f = open(os.path.join(target_dir, 'tracked'))
        lines = f.readlines()
        f.close()
        self.assertEquals(lines[0].strip(), 'last')

    def test_clean(self):
        target_dir = os.path.join(self.dst_dir, "My clone")
        repo = GitRepo(target_dir, self.src_repo)
        try:
            repo.clean()
        except:
            self.fail("clean() should not fail if "
                      "clone not already done")

        repo('master')

        dirty_dir = os.path.join(repo.target_dir, 'dirty')
        os.mkdir(dirty_dir)
        dirty_files = (os.path.join(repo.target_dir, 'untracked'),
                       os.path.join(dirty_dir, 'untracked2'))
        for path in dirty_files:
            with open(path, 'w') as f:
                f.write('content')
        repo.clean()
        for path in dirty_files:
            self.failIf(os.path.exists(path),
                        "Untracked file should have been removed")
        self.failIf(os.path.exists(dirty_dir),
                    "Untracked dir should have been removed")

    def test_clone_on_sha(self):
        """Git clone."""
        target_dir = os.path.join(self.dst_dir, "My clone")
        repo = GitRepo(target_dir, self.src_repo)
        repo('master')
        sha = repo.parents()[0]
        target_dir = os.path.join(self.dst_dir, "My clone 2")
        repo = GitRepo(target_dir, self.src_repo)
        repo(sha)
        sha2 = repo.parents()[0]
        self.assert_(sha == sha2, 'Bad clone on SHA')

    def test_uncommitted_changes(self):
        """GitRepo can detect uncommitted changes."""
        # initial cloning
        target_dir = os.path.join(self.dst_dir, "clone to update")
        repo = GitRepo(target_dir, self.src_repo)
        repo('master')

        self.assertFalse(repo.uncommitted_changes())

        f = open(os.path.join(target_dir, 'tracked'), 'w')
        f.write('mod')
        f.close()

        self.assertTrue(repo.uncommitted_changes())


class GitBranchTestCase(GitBaseTestCase):

    def create_src(self):
        GitBaseTestCase.create_src(self)
        os.chdir(self.src_repo)
        self.make_branch(self.src_repo, 'somebranch')

    def make_branch(self, src_dir, name):
        """create a branch
        """
        subprocess.check_call(['git', 'branch', name], cwd=src_dir)

    def test_switch_local_branch(self):
        """Switch to a branch created before the clone.

        In this case, the branch already exists in local repo
        """

        # Testing starts here
        target_dir = os.path.join(self.dst_dir, "to_branch")
        branch = GitRepo(target_dir, self.src_repo)
        #update file from master after branching
        branch("master")
        with working_directory_keeper:
            os.chdir(target_dir)
            f = open('tracked', 'w')
            f.write("last after branch" + os.linesep)
            f.close()
            subprocess.call(['git', 'add', 'tracked'])
            subprocess.call(['git', 'commit', '-m', 'last version'])

        # check that no changes exists when switching from one to other
        branch('somebranch')
        self.assertFalse(branch.uncommitted_changes())
        branch('master')
        self.assertFalse(branch.uncommitted_changes())

        #modify the branch
        branch('somebranch')
        self.assertFalse(branch.uncommitted_changes())
        self.assertFalse(branch.uncommitted_changes())
        with working_directory_keeper:
            os.chdir(target_dir)
            subprocess.call(['git', 'config', 'user.email', COMMIT_USER_EMAIL])
            subprocess.call(['git', 'config', 'user.name', COMMIT_USER_NAME])
            f = open('tracked')
            lines = f.readlines()
            f.close()
            self.assertEquals(lines[0].strip(), 'last')
            f = open('tracked', 'w')
            f.write("last from branch" + os.linesep)
            f.close()
            subprocess.call(['git', 'add', 'tracked'])
            subprocess.call(['git', 'commit', '-m', 'last version'])
            f = open('tracked')
            lines = f.readlines()
            f.close()
            self.assertEquals(lines[0].strip(), 'last from branch')

        # switch to master
        branch('master')
        self.assertFalse(branch.uncommitted_changes())
        f = open(os.path.join(target_dir, 'tracked'))
        lines = f.readlines()
        f.close()
        self.assertEquals(lines[0].strip(), 'last after branch')
        self.assertFalse(branch.uncommitted_changes())

    def test_switch_remote_branch(self):
        """Switch to a branch created after the clone.

        In this case, the branch doesn't exist in local repo
        """
        # init the local clone
        # Testing starts here
        target_dir = os.path.join(self.dst_dir, "to_branch")
        branch = GitRepo(target_dir, self.src_repo)
        #update file from master after branching
        branch("master")

        # create the remote branch with some modifications
        self.make_branch(self.src_repo, 'remotebranch')
        with working_directory_keeper:
            os.chdir(self.src_repo)
            subprocess.call(['git', 'checkout', 'remotebranch'])
            f = open('tracked', 'w')
            f.write("last after remote branch" + os.linesep)
            f.close()
            subprocess.call(['git', 'add', 'tracked'])
            subprocess.call(['git', 'commit', '-m', 'last version'])

        # switch to the remote branch and check tracked file
        branch("remotebranch")

        with working_directory_keeper:
            os.chdir(target_dir)
            f = open('tracked')
            lines = f.readlines()
            f.close()
            self.assertEquals(lines[0].strip(), "last after remote branch")
