"""VCS tests: Git."""

import os
import subprocess
from zc.buildout import UserError
from ..testing import COMMIT_USER_EMAIL
from ..testing import COMMIT_USER_NAME
from ..testing import VcsTestCase
from ..git import GitRepo
from ..git import BUILDOUT_ORIGIN
from ..base import UpdateError
from ...utils import working_directory_keeper, WorkingDirectoryKeeper
from ...utils import check_output


def git_set_user_info(repo_dir):
    """Write user information locally in repo, to allow commit creations.

    Commit creations can be issued by more commands than just ``commit``, e.g,
    ``merge`` or ``pull``.
    Git will fail if the user email and name aren't properly set at that time.
    """
    with WorkingDirectoryKeeper():  # independent from other instances
        os.chdir(repo_dir)
        subprocess.call(['git', 'config', 'user.email', COMMIT_USER_EMAIL])
        subprocess.call(['git', 'config', 'user.name', COMMIT_USER_NAME])


def git_write_commit(repo_dir, filepath, contents, msg="Unit test commit"):
    """Write specified file with contents, commit and return commit SHA.

    :param filepath: path of file to write to, relative to repository
    """
    with WorkingDirectoryKeeper():  # independent from the main instance
        os.chdir(repo_dir)
        # needs to be done just once, but I prefer to do it a few useless
        # times than to forget it, since it's easy to turn into a sporadic
        # test breakage on continuous integration builds.

        git_set_user_info(repo_dir)
        with open(filepath, 'w') as f:
            f.write(contents)
        subprocess.call(['git', 'add', filepath])
        subprocess.call(['git', 'commit', '-m', msg])
        return check_output(['git', 'rev-parse', '--verify', 'HEAD']).strip()


class GitBaseTestCase(VcsTestCase):
    """Common utilities for Git test cases."""

    def create_src(self):
        os.chdir(self.src_dir)
        subprocess.call(['git', 'init', 'src-repo'])
        self.src_repo = os.path.join(self.src_dir, 'src-repo')
        self.commit_1_sha = git_write_commit(self.src_repo, 'tracked',
                                             "first", msg="initial commit")
        self.commit_2_sha = git_write_commit(self.src_repo, 'tracked',
                                             "last", msg="last commit")

    def assertDepthEquals(self, repo, depth):
        """Check that the depth is indeed as expected."""
        if repo.git_version < (1, 8, 2):
            # from Git's relNotes 1.8.2.txt:
            # * "git fetch --depth" was broken in at least three ways. The
            # resulting history was deeper than specified by one commit, (...)

            # better do nothing, than check for
            # a precise offset of one, because tests have not a history
            # deep enough to make the difference with no --depth
            return

        with working_directory_keeper:
            os.chdir(repo.target_dir)
            commits = subprocess.check_output(['git', 'rev-list', 'HEAD'])
            self.assertEqual(len(commits.splitlines()), depth)


class GitTestCase(GitBaseTestCase):

    def test_init_depth(self):
        repo = GitRepo('/some/target', self.src_repo, depth='1')
        self.assertEqual(repo.options.get('depth'), 1)

        self.assertRaises(UserError, GitRepo, '/some/target', self.src_repo,
                          depth='A')
        self.assertRaises(UserError, GitRepo, '/some/target', self.src_repo,
                          depth='-1')

    def test_init_offline(self):
        repo = GitRepo('/some/target', self.src_repo, offline='true')
        self.assertTrue(repo.offline)

    def test_clone(self):
        """Git clone."""
        target_dir = os.path.join(self.dst_dir, "My clone")
        repo = GitRepo(target_dir, self.src_repo)('master')

        self.assertTrue(os.path.isdir(target_dir))
        with open(os.path.join(target_dir, 'tracked')) as f:
            self.assertEquals(f.read().strip(), 'last')

        self.assertEqual(repo.get_current_remote_fetch(), self.src_repo)

    def test_dangerous(self):
        """Test the warning message for dangerous *_HEAD revisions """
        target_dir = os.path.join(self.dst_dir, "My clone")
        repo = GitRepo(target_dir, self.src_repo)('master')
        repo.offline = True
        repo('FETCH_HEAD')  # offline mode is a simple checkout, so that works

    def test_clone_depth(self):
        """Git clone with depth option"""
        target_dir = os.path.join(self.dst_dir, "My clone")
        repo = GitRepo(target_dir, self.src_repo, depth='1')('master')

        self.assertTrue(os.path.isdir(target_dir))
        self.assertEqual(repo.parents(), [self.commit_2_sha])
        self.assertDepthEquals(repo, 1)

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

        # see launchpad #1215873
        repo(new_sha)

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

    def test_update_needs_pull(self, depth=None):
        """Update needs to be pulled from target."""
        target_dir = os.path.join(self.dst_dir, "clone to update")
        repo = GitRepo(target_dir, self.src_repo, depth=depth)
        repo('master')

        self.assertFalse(repo.uncommitted_changes())

        # update the cloned repo
        new_sha = git_write_commit(self.src_repo, 'tracked',
                                   "new content", msg="new commit")
        # We really don't have the new rev in our clone
        self.assertNotEqual(repo.parents(), [new_sha])

        # update our clone
        repo('master')
        self.assertEqual(repo.parents(), [new_sha])
        if depth is not None:
            self.assertDepthEquals(repo, depth)

    def test_update_offline(self):
        """Offline update allows to navigate across commits"""
        target_dir = os.path.join(self.dst_dir, "clone to update")
        repo = GitRepo(target_dir, self.src_repo)
        repo('master')

        # base assumptions
        self.assertFalse(repo.uncommitted_changes())
        self.assertEqual(repo.parents(), [self.commit_2_sha])

        repo.offline = True
        repo(self.commit_1_sha)
        self.assertEqual(repo.parents(), [self.commit_1_sha])

        repo('master')
        self.assertEqual(repo.parents(), [self.commit_2_sha])

        repo.url = 'file:///as/if/it/repointed/elsewhere/before'
        self.assertRaises(UserError, repo, 'master')

    def test_clone_offline_exc(self):
        """Attempting to clone offline is an :class:`UserError`."""
        target_dir = os.path.join(self.dst_dir, "offline clone")
        repo = GitRepo(target_dir, self.src_repo, offline=True)
        self.assertRaises(UserError, repo, 'master')

    def test_update_needs_pull_depth(self):
        """Update needs to be pulled from target (case with depth option)"""
        self.test_update_needs_pull(depth=1)

    def test_update_no_ff(self):
        """Recov if fast fwd is not possible and vcs-clear-retry is True

        To create the condition we make a first clone on a commit and later
        on move master sideways in the source (in real life this ends up
        with the original commit being eventually gc'ed)
        """
        target_dir = os.path.join(self.dst_dir, "clone to update")
        repo = GitRepo(target_dir, self.src_repo)
        repo('master')

        with working_directory_keeper:
            os.chdir(self.src_repo)
            subprocess.check_call(['git', 'checkout', self.commit_1_sha])
        new_sha = git_write_commit(self.src_repo, 'tracked',
                                   "new content", msg="new commit")
        with working_directory_keeper:
            os.chdir(self.src_repo)
            subprocess.check_call(['git', 'branch', '-f', 'master'])
            # not really necessary for the test, but still better for
            # consistency
            subprocess.check_call(['git', 'checkout', 'master'])

        self.assertRaises(UpdateError, repo, 'master')
        repo.clear_retry = True
        repo('master')
        self.assertEqual(repo.parents(), [new_sha])

        # future updates work wihout help (we are back to normal conditions)
        repo.clear_retry = False
        new_sha2 = git_write_commit(self.src_repo, 'tracked',
                                    "back to normal", msg="regular commit")
        repo('master')
        self.assertEqual(repo.parents(), [new_sha2])

    def test_query_unknown_remote_ref(self):
        """Querying of remote works.

        This is an internal API test.
        """
        target_dir = os.path.join(self.dst_dir, "clone to query from")
        # we need the origin initialisation done from get_update()
        repo = GitRepo(target_dir, self.src_repo)('master')
        self.assertEqual(repo.query_remote_ref(BUILDOUT_ORIGIN, 'master'),
                         ('branch', self.commit_2_sha))
        self.assertEqual(repo.query_remote_ref(BUILDOUT_ORIGIN, 'deadbeef'),
                         (None, 'deadbeef'))

    def test_clone_remote_HEAD(self):
        """Remote HEAD should be usable to clone onto."""
        target_dir = os.path.join(self.dst_dir, "clone to make on HEAD")
        repo = GitRepo(target_dir, self.src_repo)
        subprocess.check_call(['git', 'checkout', self.commit_1_sha],
                              cwd=self.src_repo)
        repo('HEAD')
        self.assertEqual(repo.parents(), [self.commit_1_sha])

    def test_clone_update_remote_HEAD(self):
        """Remote HEAD should be usable to clone onto."""
        target_dir = os.path.join(self.dst_dir, "clone to make on HEAD")
        repo = GitRepo(target_dir, self.src_repo)('master')
        subprocess.check_call(['git', 'checkout', self.commit_1_sha],
                              cwd=self.src_repo)
        repo('HEAD')
        self.assertEqual(repo.parents(), [self.commit_1_sha])


class GitBranchTestCase(GitBaseTestCase):

    def create_src(self):
        GitBaseTestCase.create_src(self)
        os.chdir(self.src_repo)
        self.make_branch(self.src_repo, 'somebranch')

    def make_branch(self, src_dir, name):
        """create a branch and switch src repo to it.

        Subsequent commits in src repo will happen in that branch
        """
        subprocess.check_call(['git', 'checkout', '-b', name], cwd=src_dir)

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
        git_write_commit(target_dir, 'tracked',
                         "last after branch", msg="last version")
        branch('somebranch')
        git_write_commit(target_dir, 'tracked',
                         "last from branch", msg="last version")
        with open(target_file) as f:
            self.assertEqual(f.read().strip(), "last from branch")

        # switch to master
        branch('master')
        self.assertFalse(branch.uncommitted_changes())
        with open(target_file) as f:
            self.assertEqual(f.read().strip(), "last after branch")

    def test_switch_local_branch_depth(self):
        """Switch to a branch created before the clone.

        In this case, the branch already exists in local repo but there are new
        commits for it in remote.
        """
        target_dir = os.path.join(self.dst_dir, "to_branch")
        target_file = os.path.join(target_dir, 'tracked')
        branch = GitRepo(target_dir, self.src_repo)

        # update file from master in local repo after branching
        branch("master")
        git_write_commit(target_dir, 'tracked',
                         "last after branch", msg="last after")

        # commit in the remote branch
        git_write_commit(self.src_repo, 'tracked',
                         "new in branch", msg="last from branch")

        branch('somebranch')
        with open(target_file) as f:
            self.assertEqual(f.read().strip(), "new in branch")

        # switch back to remote master. Local commit has not disappeared,
        # but I don't think is reasonible to actually make this a stable
        # promise, especially if lots of history happened between the switches
        branch('master')
        self.assertFalse(branch.uncommitted_changes())
        with open(target_file) as f:
            self.assertEqual(f.read().strip(), "last after branch")

    def test_switch_remote_branch(self, depth=None):
        """Switch to a branch created after the clone.

        In this case, the branch doesn't exist in local repo
        """
        target_dir = os.path.join(self.dst_dir, "to_branch")
        branch = GitRepo(target_dir, self.src_repo, depth=depth)
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

    def test_switch_remote_branch_depth(self):
        """Switch to a branch created after the clone.

        Case where depth option is in play.
        """
        self.test_switch_remote_branch(depth=1)

    def test_clone_on_branch(self, depth=None):
        """Test that direct cloning on branch works."""
        target_dir = os.path.join(self.dst_dir, "to_branch")
        repo = GitRepo(target_dir, self.src_repo, depth=depth)
        # update file in src after branching
        sha = git_write_commit(self.src_repo, 'tracked',
                               "in branch", msg="last version")
        repo("somebranch")
        self.assertEqual(repo.parents(), [sha])

    def test_clone_on_branch_update_HEAD(self):
        """Update on remote HEAD works even if that's a branch change"""
        target_dir = os.path.join(self.dst_dir, "to_branch")
        repo = GitRepo(target_dir, self.src_repo)
        # update file in src after branching
        sha_branch = git_write_commit(self.src_repo, 'tracked',
                                      "in branch", msg="last version")
        repo("somebranch")
        # verify test base assumption: we are indeed where we think
        self.assertEqual(repo.parents(), [sha_branch])
        subprocess.check_call(['git', 'checkout', 'master'],
                              cwd=self.src_repo)
        sha_master = git_write_commit(self.src_repo, 'tracked',
                                      "after branch",
                                      msg="new commit on master")

        repo('HEAD')
        self.assertEqual(repo.parents(), [sha_master])

        # maybe that's unnecessary, but fun for now:
        descr = check_output(['git', 'describe', '--all'], cwd=target_dir)
        self.assertEqual(descr.strip(), 'remotes/origin/HEAD')

    def test_clone_on_branch_depth(self):
        self.test_clone_on_branch(depth=1)

    def test_sha_pinning_branch_indication(self):
        """SHA pinning with branch indication

        It must work even if in origin, the specified commit is unreachable
        from HEAD.

        GR: I believe that in some cases, the bare fetch used if there's no
        branch indication might not retrieve the wished SHA, but I couldn't
        reproduce this kind of condition with a setup that wouldn't otherwise
        make the other operations of :class:`GitRepo` fail.
        """
        target_dir = os.path.join(self.dst_dir, "to_branch")
        sha = git_write_commit(self.src_repo, 'tracked',
                               "in branch", msg="last in branch")
        # rewinding src repo to master branch so that sha is unreachable
        # from HEAD
        subprocess.check_call(['git', 'checkout', 'master'], cwd=self.src_repo)
        sha_master = git_write_commit(self.src_repo, 'tracked',
                                      'on master', msg="new in master")

        repo = GitRepo(target_dir, self.src_repo, branch='somebranch')
        repo(sha)
        self.assertEqual(repo.parents(), [sha])
        self.assertNotEqual(
            subprocess.call(['git', 'cat-file', '-e', sha_master],
                            cwd=target_dir),
            0, msg="SHA should not have been fetched")


class GitMergeTestCase(GitBaseTestCase):

    def create_src(self):
        GitBaseTestCase.create_src(self)
        os.chdir(self.src_repo)

        self.make_branch(self.src_repo, 'branch1')
        self.checkout_branch(self.src_repo, 'branch1')
        git_write_commit(self.src_repo, 'file_on_branch1',
                         "file on branch 1", msg="on branch 1")
        self.checkout_branch(self.src_repo, 'master')

        self.make_branch(self.src_repo, 'branch2')
        self.checkout_branch(self.src_repo, 'branch2')
        git_write_commit(self.src_repo, 'file_on_branch2',
                         "file on branch 2", msg="on branch 2")
        self.checkout_branch(self.src_repo, 'master')

    def make_branch(self, src_dir, name):
        """create a branch
        """
        subprocess.check_call(['git', 'branch', name], cwd=src_dir)

    def checkout_branch(self, src_dir, name):
        """checkout a branch
        """
        subprocess.check_call(['git', 'checkout', name], cwd=src_dir)

    def test_01_check_src_repo(self):
        """test if the creation of source repo worked as expected"""
        target_dir = os.path.join(self.dst_dir, "to_repo")
        repo = GitRepo(target_dir, self.src_repo)

        repo('master')
        self.assertFalse(os.path.exists(os.path.join(target_dir,
                                                     'file_on_branch1')),
                         'file_on_branch1 should not exist')
        self.assertFalse(os.path.exists(os.path.join(target_dir,
                                                     'file_on_branch2')),
                         'file_on_branch2 should not exist')

        repo('branch1')
        self.assertTrue(os.path.exists(os.path.join(target_dir,
                                                    'file_on_branch1')),
                        'file_on_branch1 should exist')
        self.assertFalse(os.path.exists(os.path.join(target_dir,
                                                     'file_on_branch2')),
                         'file_on_branch2 should not exist')

        repo('branch2')
        self.assertFalse(os.path.exists(os.path.join(target_dir,
                                                     'file_on_branch1')),
                         'file_on_branch1 should not exist')
        self.assertTrue(os.path.exists(os.path.join(target_dir,
                                                    'file_on_branch2')),
                        'file_on_branch2 should exist')

    def test_02_merge(self):
        target_dir = os.path.join(self.dst_dir, "to_repo")
        repo = GitRepo(target_dir, self.src_repo)
        repo('master')
        git_set_user_info(repo.target_dir)

        repo.merge('branch1')
        self.assertTrue(os.path.exists(os.path.join(target_dir,
                                                    'file_on_branch1')),
                        'file_on_branch1 should exist')
        self.assertFalse(os.path.exists(os.path.join(target_dir,
                                                     'file_on_branch2')),
                         'file_on_branch2 should not exist')
        repo.merge('branch2')
        self.assertTrue(os.path.exists(os.path.join(target_dir,
                                                    'file_on_branch1')),
                        'file_on_branch1 should exist')
        self.assertTrue(os.path.exists(os.path.join(target_dir,
                                                    'file_on_branch2')),
                        'file_on_branch2 should exist')

    def test_03_revert(self):
        target_dir = os.path.join(self.dst_dir, "to_repo")
        repo = GitRepo(target_dir, self.src_repo)
        repo('master')
        git_set_user_info(repo.target_dir)

        repo.merge('branch1')
        self.assertTrue(os.path.exists(os.path.join(target_dir,
                                                    'file_on_branch1')),
                        'file_on_branch1 should exist')

        repo.revert('master')
        self.assertFalse(os.path.exists(os.path.join(target_dir,
                                                     'file_on_branch1')),
                         'file_on_branch1 should not exist')


class GitTagTestCase(GitBaseTestCase):

    def create_src(self):
        GitBaseTestCase.create_src(self)
        os.chdir(self.src_repo)
        self.make_tag('sometag')

    def make_tag(self, tag):
        subprocess.check_call(['git', 'tag', tag, self.commit_1_sha])

    def test_query_remote(self):
        target_dir = os.path.join(self.dst_dir, "to_repo")
        repo = GitRepo(target_dir, self.src_repo)
        with working_directory_keeper:
            subprocess.check_call(['git', 'init', target_dir])
            os.chdir(target_dir)
            subprocess.check_call(['git', 'remote', 'add',
                                   'orig', self.src_repo])
            self.assertRemoteQueryResult(
                repo.query_remote_ref('orig', 'sometag'), self.commit_1_sha)

    def assertRemoteQueryResult(self, result, expected_sha):
        """If possible, check that the result of query matches expected_sha.

        To be subclassed for annotated tags. One can assume that current
        working dir is the repo.
        """
        self.assertEqual(result, ('tag', expected_sha))

    def test_clone_to_tag(self, depth=None):
        target_dir = os.path.join(self.dst_dir, "to_repo")
        repo = GitRepo(target_dir, self.src_repo, depth=depth)
        repo('sometag')
        self.assertEqual(repo.parents(), [self.commit_1_sha])

        self.assertTrue(repo.is_local_fixed_revision('sometag'))

    def test_revert_to_tag(self):
        target_dir = os.path.join(self.dst_dir, "to_repo")
        repo = GitRepo(target_dir, self.src_repo)('master')
        # tag is not fetched yet, let's do it
        subprocess.check_call(['git', 'fetch', BUILDOUT_ORIGIN,
                               '+refs/tags/sometag:refs/tags/sometag'],
                              cwd=target_dir)
        repo.revert('sometag')
        self.assertEqual(repo.parents(), [self.commit_1_sha])

        with open(os.path.join(target_dir, 'tracked'), 'w') as f:
            f.write("local modification")
        self.assertTrue(repo.uncommitted_changes())

        repo.revert('sometag')
        self.assertFalse(repo.uncommitted_changes())

    def test_clone_to_tag_depth(self):
        self.test_clone_to_tag(depth='1')

    def test_update_to_tag(self, depth=None):
        target_dir = os.path.join(self.dst_dir, "to_repo")
        repo = GitRepo(target_dir, self.src_repo, depth=depth)
        repo('master')
        # checking that test base assumptions are right
        self.assertEqual(repo.parents(), [self.commit_2_sha])

        repo('sometag')
        self.assertEqual(repo.parents(), [self.commit_1_sha])
        subprocess.check_call(['git', 'checkout', 'sometag'],
                              cwd=repo.target_dir)

    def test_update_to_tag_depth(self):
        self.test_clone_to_tag(depth='1')

    def test_update_tag_to_head(self, depth=None):
        target_dir = os.path.join(self.dst_dir, "to_repo")
        repo = GitRepo(target_dir, self.src_repo, depth=depth)
        repo('sometag')
        subprocess.check_call(['git', 'checkout', 'sometag'],
                              cwd=repo.target_dir)
        self.assertEqual(
            check_output(['git', 'tag'], cwd=repo.target_dir).strip(),
            'sometag')
        repo('master')
        self.assertEqual(repo.parents(), [self.commit_2_sha])

    def test_update_tag_to_head_depth(self):
        self.test_update_tag_to_head(depth='1')

    def test_update_tag_to_tag_depth_backwards(self):
        with working_directory_keeper:
            os.chdir(self.src_repo)
            subprocess.check_call(['git', 'tag', 'tag2', self.commit_2_sha])

        target_dir = os.path.join(self.dst_dir, "to_repo")
        repo = GitRepo(target_dir, self.src_repo, depth='1')
        repo('tag2')
        repo('sometag')
        self.assertEqual(repo.parents(), [self.commit_1_sha])
        self.assertDepthEquals(repo, 1)


class GitAnnotatedTagTestCase(GitTagTestCase):
    """Same as :class:`GitTagTestCase`, with annotated tags.

    Annotated tags behave a bit differently that lightweight ones.
    """

    def make_tag(self, tag):
        subprocess.check_call(['git', 'tag', '-a', '-m', "Annotation",
                               tag, self.commit_1_sha])

    def assertRemoteQueryResult(self, result, expected_sha):
        """If possible, check that the result of query matches expected_sha.

        In cas of annotated tags, the pointer is not on the tagged commit,
        but on the tag.
        """
        # that will be enough for now : there are also tests for
        # get_update(). This test is to fasten up debugging
        self.assertEqual(result[0], ('tag'))
