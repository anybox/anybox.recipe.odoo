"""VCS tests: Git."""

import os
import subprocess
from ..testing import COMMIT_USER_EMAIL
from ..testing import COMMIT_USER_NAME
from ..testing import VcsTestCase
from ..git import GitRepo
from ...utils import working_directory_keeper, WorkingDirectoryKeeper
from ...utils import check_output


def git_write_commit(repo_dir, filename, contents, msg="Unit test commit"):
    """Write specified file with contents, commit and return commit SHA.

    ``filename`` is actually a relative path from ``repo_dir``.
    """

    with WorkingDirectoryKeeper():  # independent from the main instance
        os.chdir(repo_dir)
        # repo configuration is local by default
        # needs to be done just once, but I prefer to do it a few useless
        # times than to forget it, since it's easy to turn into a sporadic
        # test breakage on continuous integration builds.
        subprocess.call(['git', 'config', 'user.email', COMMIT_USER_EMAIL])
        subprocess.call(['git', 'config', 'user.name', COMMIT_USER_NAME])
        with open(filename, 'w') as f:
            f.write(contents)
        subprocess.call(['git', 'add', filename])
        subprocess.call(['git', 'commit', '-m', msg])
        return check_output(['git', 'rev-parse', '--verify', 'HEAD']).strip()


class GitBaseTestCase(VcsTestCase):
    """Common utilities for Git test cases."""

    def create_src(self):
        os.chdir(self.src_dir)
        subprocess.call(['git', 'init', 'src-branch'])
        self.src_repo = os.path.join(self.src_dir, 'src-branch')
        self.commit_1_sha = git_write_commit(self.src_repo, 'tracked',
                                             "first", msg="initial commit")
        self.commit_2_sha = git_write_commit(self.src_repo, 'tracked',
                                             "last", msg="last commit")


class GitTestCase(GitBaseTestCase):

    def test_clone(self):
        """Git clone."""
        target_dir = os.path.join(self.dst_dir, "My clone")
        GitRepo(target_dir, self.src_repo)('master')

        self.assertTrue(os.path.isdir(target_dir))
        with open(os.path.join(target_dir, 'tracked')) as f:
            self.assertEquals(f.read().strip(), 'last')

    def test_archive(self):
        """Git clone, then archive"""
        repo = GitRepo(os.path.join(self.dst_dir, "My clone"), self.src_repo)
        repo('master')

        archive_dir = os.path.join(self.dst_dir, "archive directory")
        repo.archive(archive_dir)
        with open(os.path.join(archive_dir, 'tracked')) as f:
            self.assertEquals(f.readlines()[0].strip(), 'last')

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
        self.assertEqual(sha, sha2, 'Bad clone on SHA')

        # next call of get_update()
        repo(sha)

    def test_clone_on_sha_update(self):
        """Git clone."""
        target_dir = os.path.join(self.dst_dir, "My clone")
        repo = GitRepo(target_dir, self.src_repo)
        repo(self.commit_1_sha)
        self.assertEqual(repo.parents(), [self.commit_1_sha])
        repo(self.commit_2_sha)
        self.assertEqual(repo.parents(), [self.commit_2_sha])

        # new commit in origin will need to be fetched
        new_sha = git_write_commit(self.src_repo, 'tracked',
                                   "new contents", msg="new commit")
        repo(new_sha)
        self.assertEqual(repo.parents(), [new_sha])

    def test_uncommitted_changes(self):
        """GitRepo can detect uncommitted changes."""
        # initial cloning
        target_dir = os.path.join(self.dst_dir, "clone to update")
        repo = GitRepo(target_dir, self.src_repo)
        repo('master')

        self.assertFalse(repo.uncommitted_changes())

        # now with a local modification
        with open(os.path.join(target_dir, 'tracked'), 'w') as f:
            f.write('mod')
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
        target_dir = os.path.join(self.dst_dir, "to_branch")
        target_file = os.path.join(target_dir, 'tracked')
        branch = GitRepo(target_dir, self.src_repo)

        # update file from master after branching
        branch("master")
        git_write_commit(target_dir, 'tracked',
                         "last after branch", msg="last version")

        # check that no changes exists when switching from one to other
        branch('somebranch')
        self.assertFalse(branch.uncommitted_changes())
        branch('master')
        self.assertFalse(branch.uncommitted_changes())

        # modify the branch
        branch('somebranch')
        self.assertFalse(branch.uncommitted_changes())
        self.assertFalse(branch.uncommitted_changes())
        git_write_commit(target_dir, 'tracked',
                         "last after branch", msg="last version")

        git_write_commit(target_dir, 'tracked',
                         "last from branch", msg="last version")
        with open(target_file) as f:
            self.assertEqual(f.read().strip(), "last from branch")

        # switch to master
        branch('master')
        self.assertFalse(branch.uncommitted_changes())
        with open(target_file) as f:
            self.assertEqual(f.read().strip(), "last after branch")

    def test_switch_remote_branch(self):
        """Switch to a branch created after the clone.

        In this case, the branch doesn't exist in local repo
        """
        target_dir = os.path.join(self.dst_dir, "to_branch")
        branch = GitRepo(target_dir, self.src_repo)
        # update file from master after branching
        branch("master")

        # create the remote branch with some modifications
        self.make_branch(self.src_repo, 'remotebranch')
        with working_directory_keeper:
            os.chdir(self.src_repo)
            subprocess.call(['git', 'checkout', 'remotebranch'])

        git_write_commit(self.src_repo, 'tracked',
                         "last after remote branch", msg="last version")

        # switch to the remote branch and check tracked file has been updated
        branch("remotebranch")
        with open(os.path.join(target_dir, 'tracked')) as f:
            self.assertEquals(f.read().strip(), "last after remote branch")
