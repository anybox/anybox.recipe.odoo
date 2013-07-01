"""VCS tests: Git."""

import os
import subprocess
from ..testing import COMMIT_USER_EMAIL
from ..testing import COMMIT_USER_NAME
from ..testing import VcsTestCase
from ..git import GitRepo


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
