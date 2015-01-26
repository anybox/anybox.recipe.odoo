"""VCS tests: Bazaar."""

import os
import subprocess
from zc.buildout import UserError
from ..testing import COMMIT_USER_FULL
from ..testing import VcsTestCase
from ..bzr import BzrBranch
from ..bzr import working_directory_keeper
from ..base import UpdateError
from ..base import CloneError


class BzrBaseTestCase(VcsTestCase):
    """Common utilities for Bazaard test cases."""

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

    def assertRevision(self, branch, rev, first_line, msg=None):
        """Assert that branch is at prescribed revision

        :param branch: instance of :class:`BzrBranch` to work on
        :param rev: revision number (revno)
        :param first_line: expected first line of the 'tracked' file
        :param msg: passed to underlying assertions

        Double check with expected first line of 'tracked' file."""
        target_dir = branch.target_dir
        self.assertTrue(os.path.isdir(target_dir), msg=msg)
        f = open(os.path.join(target_dir, 'tracked'))
        lines = f.readlines()
        f.close()
        self.assertEquals(lines[0].strip(), first_line, msg=msg)
        self.assertEquals(branch.parents(as_revno=True), [rev], msg=msg)

    def assertRevision1(self, branch, **kw):
        """Assert that branch is at revision 1."""
        self.assertRevision(branch, '1', 'first', **kw)

    def assertRevision2(self, branch, **kw):
        """Assert that branch is at revision 2."""
        self.assertRevision(branch, '2', 'last', **kw)


class BzrTestCase(BzrBaseTestCase):

    def test_branch(self):
        target_dir = os.path.join(self.dst_dir, "My branch")
        branch = BzrBranch(target_dir, self.src_repo)
        branch('last:1')
        self.assertRevision2(branch)

    def test_branch_on_revision_retry(self):
        """Test retry system if direct branching to revison fails."""
        target_dir = os.path.join(self.dst_dir, "My branch")
        branch = BzrBranch(target_dir, self.src_repo)

        normal_method = branch._branch
        monkey_called = []

        def branch_no_rev(revision):
            """Monkey patch to simulate the error."""
            monkey_called.append(revision)
            if revision:
                raise CloneError("fake branch cmd", 3)
            return normal_method(revision)

        branch._branch = branch_no_rev
        branch('last:1')

        # ensures that we actually did test something:
        self.assertEqual(monkey_called, ['last:1', None])
        self.assertRevision2(branch)  # branching worked

    def test_parents_revid(self):
        target_dir = os.path.join(self.dst_dir, "My branch")
        branch = BzrBranch(target_dir, self.src_repo)
        branch('last:1')
        self.assertRevision2(branch, msg="Test impaired by other problem")

        parents = branch.parents()
        self.assertEquals(len(parents), 1)
        self.assertTrue(parents[0].startswith('revid:test@example.org-'),
                        msg="Result does not look to be a revid")

    def test_parents_pip(self):
        target_dir = os.path.join(self.dst_dir, "My branch")
        branch = BzrBranch(target_dir, self.src_repo)
        branch('last:1')
        self.assertRevision2(branch, msg="Test impaired by other problem")

        parents = branch.parents(pip_compatible=True)
        self.assertEquals(parents, ['2'])

    def test_branch_options_conflict(self):
        target_dir = os.path.join(self.dst_dir, "My branch")
        branch = BzrBranch(target_dir, self.src_repo,
                           **{'bzr-init': 'branch',
                              'bzr-stacked-branches': 'True'})
        self.assertRaises(Exception, branch, "last:1")

    def test_branch_bzr_init(self):
        target_dir = os.path.join(self.dst_dir, "My branch")
        branch = BzrBranch(target_dir, self.src_repo,
                           **{'bzr-init': 'branch'})
        branch('last:1')
        self.assertRevision2(branch)

    def test_branch_stacked_deprecated(self):
        target_dir = os.path.join(self.dst_dir, "My branch")
        branch = BzrBranch(target_dir, self.src_repo,
                           **{'bzr-stacked-branches': 'True'})
        branch('last:1')
        self.assertRevision2(branch)

    def test_branch_stacked(self):
        target_dir = os.path.join(self.dst_dir, "My branch")
        branch = BzrBranch(target_dir, self.src_repo,
                           **{'bzr-init': 'stacked-branch'})
        branch('last:1')
        self.assertRevision2(branch)

    def test_checkout_lightweight(self):
        target_dir = os.path.join(self.dst_dir, "My branch")
        branch = BzrBranch(target_dir, self.src_repo,
                           **{'bzr-init': 'lightweight-checkout'})
        branch('1')
        self.assertRevision1(branch)

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

    def test_update_tag(self):
        """Update to an avalailable rev, identified by tag.
        """
        with working_directory_keeper:
            os.chdir(self.src_repo)
            subprocess.check_call(['bzr', 'tag', '-r', '1', 'sometag'])

        target_dir = os.path.join(self.dst_dir, "clone to update")

        # Testing starts here
        branch = BzrBranch(target_dir, self.src_repo)
        branch('sometag')
        self.assertRevision1(branch)

    def test_update_needs_pull(self):
        """Update to a revision that needs to be pulled from target."""
        target_dir = os.path.join(self.dst_dir, "clone to update")
        branch = BzrBranch(target_dir, self.src_repo)('1')
        # We really don't have rev 2 in branch
        self.assertRaises(LookupError, branch.get_revid, '2')

        branch('2')
        self.assertRevision2(branch)

    def test_update_revid_needs_pull(self):
        """Update to a rev that needs to be pulled from source, by revid."""
        target_dir = os.path.join(self.dst_dir, "clone to update")
        branch = BzrBranch(target_dir, self.src_repo)('1')
        # We really don't have rev 2 in branch
        self.assertRaises(LookupError, branch.get_revid, '2')

        revid = BzrBranch(self.src_repo, self.src_repo).get_revid('2')
        branch('revid:' + revid)
        self.assertRevision2(branch)

    def test_clean(self):
        """Test clean method, and esp. that no local mod occurs.

        See launchpad: #1192973, bzr tracks empty directories. We must not
        remove them.
        """
        with working_directory_keeper:
            os.chdir(self.src_repo)
            os.mkdir('subdir')
            subprocess.check_call(['bzr', 'add'])
            subprocess.call(['bzr', 'whoami', '--branch', COMMIT_USER_FULL])
            subprocess.check_call(['bzr', 'commit', '-m', "bidule"])
        target_dir = os.path.join(self.dst_dir, "clone to clean")
        branch = BzrBranch(target_dir, self.src_repo)
        try:
            branch.clean()
        except:
            self.fail("clean() should not fail if "
                      "branch not already done")

        branch('last:1')
        untracked = os.path.join(branch.target_dir, 'subdir', 'untracked.pyc')
        with open(untracked, 'w') as f:
            f.write('untracked content')
        branch.clean()
        self.assertFalse(os.path.exists(untracked))
        with working_directory_keeper:
            os.chdir(branch.target_dir)
            bzr_status = subprocess.Popen(['bzr', 'status'],
                                          stdout=subprocess.PIPE)
            out = bzr_status.communicate()[0]

        self.assertEquals(bzr_status.returncode, 0)
        # output of 'bzr status' should be empty : neither unknown file nor
        # any local modification, including removal of 'subdir'
        self.assertEquals(out.strip(), '')

    def test_uncommitted_changes_tracked(self):
        target_dir = os.path.join(self.dst_dir, "clone to dirty")
        branch = BzrBranch(target_dir, self.src_repo)('last:1')
        self.assertFalse(branch.uncommitted_changes())
        with open(os.path.join(target_dir, 'tracked'), 'w') as f:
            f.write('some change')
        self.assertTrue(branch.uncommitted_changes())

    def test_uncommitted_changes_untracked(self):
        target_dir = os.path.join(self.dst_dir, "clone to dirty")
        branch = BzrBranch(target_dir, self.src_repo)('last:1')
        self.assertFalse(branch.uncommitted_changes())
        with open(os.path.join(target_dir, 'unknownfile'), 'w') as f:
            f.write('some change')
        self.assertTrue(branch.uncommitted_changes())

    def test_revert(self):
        target_dir = os.path.join(self.dst_dir, "clone to clean")
        branch = BzrBranch(target_dir, self.src_repo)
        branch('last:1')

        path = os.path.join(target_dir, 'tracked')
        with open(path, 'r') as f:
            original = f.readlines()
        with open(path, 'w') as f:
            f.write('a local mod')

        branch.revert('last:1')
        with open(path, 'r') as f:
            self.assertEqual(f.readlines(), original)

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

        # second rename, on a fixed revno. The pull should be issued in that
        # case, even if we already have that revno in original source
        # (see lp:1320198)
        new_src2 = os.path.join(self.src_dir, 'new-src-repo2')
        os.rename(new_src, new_src2)
        branch = BzrBranch(target_dir, new_src2)

        orig_pull = branch._pull

        def logging_pull():
            self.pulled = True
            return orig_pull()
        branch._pull = logging_pull

        self.pulled = False
        branch('1')
        self.assertTrue(self.pulled)

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
        save = vcs.bzr.LPDIR
        vcs.bzr.LPDIR = None
        self.assertRaises(RuntimeError, BzrBranch, '',
                          'lp:anybox.recipe.openerp')
        vcs.bzr.LPDIR = save

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

    def test_merge(self):
        current = os.getcwd()
        to_merge = os.path.join(self.dst_dir, "proposed branch")
        BzrBranch(to_merge, self.src_repo)('last:1')
        os.chdir(to_merge)
        added_file = 'added'
        f = open(added_file, 'w')
        f.write("content" + os.linesep)
        f.close()
        subprocess.call(['bzr', 'add'])
        subprocess.call(['bzr', 'whoami', '--branch', COMMIT_USER_FULL])
        subprocess.call(['bzr', 'commit', '-m', 'poposal commit'])
        target_dir = os.path.join(self.dst_dir, "branch with merge")
        BzrBranch(target_dir, self.src_repo)('last:1')
        BzrBranch(
            target_dir, to_merge, **{'bzr-init': 'merge'})('last:1')
        os.chdir(current)
        self.assertTrue(os.path.exists(os.path.join(target_dir, added_file)))


class BzrOfflineTestCase(BzrBaseTestCase):

    def make_local_branch(self, path, initial_rev, options=None):
        """Make a local branch of the source at initial_rev and forbid pulls.
        """
        if options is None:
            options = {}
        target_dir = os.path.join(self.dst_dir, path)
        # initial branching (non offline
        build_branch = BzrBranch(target_dir, self.src_repo)
        build_branch(initial_rev)
        build_branch.update_conf()  # just to get an absolute path in there

        # crippled offline branch
        branch = BzrBranch(target_dir, self.src_repo, offline=True, **options)

        def _pull():
            self.fail("Should not pull !")

        branch._pull = _pull
        return branch

    def test_update_needs_pull(self):
        """[offline mode] updating to a non available rev raises UpdateError.
        """
        branch = self.make_local_branch("clone to update", '1')
        self.assertRaises(UpdateError, branch, '2')

    def test_update_last(self):
        """[offline mode] update to a last:1 rev does nothing."""
        branch = self.make_local_branch("clone to update", '1')
        branch('last:1')
        self.assertRevision1(branch)

    def test_update_available_revno(self):
        """[offline mode] update to an available revno works"""
        branch = self.make_local_branch("clone to update", 'last:1')
        branch('1')
        self.assertRevision1(branch)

    def test_update_available_revno_url_change(self):
        """[offline mode] upd to an available revno with URL change is an error
        """
        branch = self.make_local_branch("clone to update", 'last:1')
        branch('1')
        self.assertRevision1(branch, msg="Test is impaired")
        new_branch = BzrBranch(branch.target_dir, 'http://other.url.example',
                               offline=True)
        self.assertRaises(UserError, new_branch, '1')
        # conf has not changed
        self.assertEquals(new_branch.parse_conf(), branch.parse_conf())

    def test_update_live_rev_url_change(self):
        """[offline mode] upd to a live revspec with URL change is an error
        """
        branch = self.make_local_branch("clone to update", 'last:1')
        branch('1')
        self.assertRevision1(branch, msg="Test is impaired")
        new_branch = BzrBranch(branch.target_dir, 'http://other.url.example',
                               offline=True)
        self.assertRaises(UserError, new_branch, 'last:1')
        self.assertEquals(new_branch.parse_conf(), branch.parse_conf())

    def test_update_available_revid_url_change(self):
        """[offline mode] upd to an available revid with URL change is ok
        """
        branch = self.make_local_branch("clone to update", 'last:1')
        branch('1')

        revid = branch.parents()[0]
        self.assertTrue(revid.startswith, 'revid:')

        new_branch = BzrBranch(branch.target_dir, 'http://other.url.example',
                               offline=True)
        new_branch(revid)
        self.assertRevision1(new_branch)

    def test_update_available_revid(self):
        """[offline mode] update to an available revid works.
        """
        branch = self.make_local_branch("clone to update", 'last:1')
        revid = branch.get_revid('1')
        branch('revid:' + revid)
        self.assertRevision1(branch)

    def test_update_available_tag_is_local_fixed_revision(self):
        """[offline mode] update to an available tag works.
        """
        branch = self.make_local_branch("clone to update", 'last:1')
        subprocess.check_call(['bzr', 'tag', '-r', '1', 'sometag'],
                              cwd=branch.target_dir)
        branch('tag:sometag')
        self.assertRevision1(branch)
        self.assertTrue(branch.is_local_fixed_revision('tag:sometag'))
        self.assertFalse(branch.is_local_fixed_revision('tag:unknown'))
        self.assertFalse(branch.is_local_fixed_revision('-1'))

    def test_lightweight_checkout_noupdate(self):
        """[offline mode] lightweight checkouts shall not be updated."""
        branch = self.make_local_branch(
            "clone to update", '1',
            options={'bzr-init': 'lightweight-checkout'})

        def _update(*a, **kw):
            self.fail("Should not update !")

        branch._update = _update

        branch('last:1')
        self.assertRevision1(branch)

    def test_lightweight_checkout_noupdate_fixed_rev(self):
        """[offline mode] lightweight checkouts shall not be updated."""
        branch = self.make_local_branch(
            "clone to update", 'last:1',
            options={'bzr-init': 'lightweight-checkout'})

        def _update(*a, **kw):
            self.fail("Should not update !")

        branch._update = _update

        branch('1')
        self.assertRevision2(branch)

    def test_lp_url_offline(self):
        """[offline mode] lp: locations are not to be resolved.

        See lp:1249566, resolving lp: performs outgoing requests,
        and resolving the remote URL is irrelevant anyway, since it won't
        be used.
        """
        brdir = os.path.join(self.dst_dir, 'lp_branch')
        os.makedirs(os.path.join(brdir, '.bzr', 'branch'))
        branch = BzrBranch(brdir, 'lp:something', offline=True)
        self.assertEqual(branch.url, 'lp:something')

        # making sure that the unresolved lp: location is not written
        # to branch.conf
        parent_loc = 'bzr+ssh://previously/resolved'
        branch.write_conf(dict(parent_location=parent_loc))

        branch.update_conf()
        self.assertEqual(branch.parse_conf()['parent_location'], parent_loc)
