import os
import subprocess
import logging
import tempfile

from zc.buildout import UserError
from .. import utils
from ..utils import working_directory_keeper
from ..utils import check_output
from .base import BaseRepo
from .base import SUBPROCESS_ENV
from .base import update_check_call
from .base import update_check_output
from .base import UpdateError

logger = logging.getLogger(__name__)

BUILDOUT_ORIGIN = 'origin'


def ishex(s):
    """True iff given string is a valid hexadecimal number.

    >>> ishex('deadbeef')
    True
    >>> ishex('01bn78')
    False
    """
    try:
        int(s, 16)
    except ValueError:
        return False
    return True


class GitRepo(BaseRepo):
    """Represent a Git clone tied to a reference branch/commit/tag."""

    vcs_control_dir = '.git'

    vcs_official_name = 'Git'

    _git_version = None

    def __init__(self, *args, **kwargs):
        super(GitRepo, self).__init__(*args, **kwargs)
        depth = self.options.pop('depth', None)
        if depth is not None and depth != 'None':
            # 'None' as a str can be used as an explicit per-repo override
            # of a global setting
            invalid = UserError("Invalid depth value %r for Git repository "
                                "at %r" % (depth, self.target_dir))
            try:
                depth = int(depth)
            except ValueError:
                raise invalid
            if depth <= 0:
                raise invalid
            self.options['depth'] = depth

    @property
    def git_version(self):
        cls = self.__class__
        version = cls._git_version
        if version is not None:
            return version

        return cls.init_git_version(utils.check_output(
            ['git', '--version']))

    @classmethod
    def init_git_version(cls, v_str):
        r"""Parse git version string and store the resulting tuple on self.

        :returns: the parsed version tuple

        Only the first 3 digits are kept. This is good enough for the few
        version dependent cases we need, and coarse enough to avoid
        more complicated parsing.

        Some real-life examples::

          >>> GitRepo.init_git_version('git version 1.8.5.3')
          (1, 8, 5)
          >>> GitRepo.init_git_version('git version 1.7.2.5')
          (1, 7, 2)

        Seen on MacOSX (not on MacPorts)::

          >>> GitRepo.init_git_version('git version 1.8.5.2 (Apple Git-48)')
          (1, 8, 5)

        Seen on Windows (Tortoise Git)::

          >>> GitRepo.init_git_version('git version 1.8.4.msysgit.0')
          (1, 8, 4)

        A compiled version::

          >>> GitRepo.init_git_version('git version 2.0.3.2.g996b0fd')
          (2, 0, 3)

        Rewrapped by `hub <https://hub.github.com/>`_, it has two lines:

          >>> GitRepo.init_git_version('git version 1.7.9\nhub version 1.11.0')
          (1, 7, 9)

        This one does not exist, allowing us to prove that this method
        actually governs the :attr:`git_version` property

          >>> GitRepo.init_git_version('git version 0.0.666')
          (0, 0, 666)
          >>> GitRepo('', '').git_version
          (0, 0, 666)

        Expected exceptions::

          >>> try: GitRepo.init_git_version('invalid')
          ... except ValueError: pass

        After playing with it, we must reset it so that tests can run with
        the proper detected one, if needed::

          >>> GitRepo.init_git_version(None)

        """
        if v_str is None:
            cls._git_version = None
            return

        v_str = v_str.strip()
        try:
            version = cls._git_version = tuple(
                int(x) for x in v_str.split()[2].split('.')[:3])
        except:
            raise ValueError("Could not parse git version output %r. Please "
                             "report this" % v_str)
        return version

    def log_call(self, cmd, callwith=subprocess.check_call,
                 log_level=logging.INFO, **kw):
            """Wrap a subprocess call with logging

            :param meth: the calling method to use.
            """
            logger.log(log_level, "%s> call %r", self.target_dir, cmd)
            return callwith(cmd, **kw)

    def clean(self):
        if not os.path.isdir(self.target_dir):
            return
        with working_directory_keeper:
            os.chdir(self.target_dir)
            subprocess.check_call(['git', 'clean', '-fdqx'])

    def parents(self, pip_compatible=False, revspec=False):
        """Return full hash of parent nodes.

        :param pip_compatible: ignored, all Git revspecs are pip compatible
        """
        with working_directory_keeper:
            os.chdir(self.target_dir)
            cmd = ['git', 'rev-parse', '--verify', 'HEAD']
            if revspec:
                cmd = ['git', 'merge-base',
                       '%s/%s' % (BUILDOUT_ORIGIN, revspec),
                       revspec]
            p = subprocess.Popen(cmd,
                                 stdout=subprocess.PIPE, env=SUBPROCESS_ENV)
            return p.communicate()[0].split()

    def uncommitted_changes(self):
        """True if we have uncommitted changes."""
        with working_directory_keeper:
            os.chdir(self.target_dir)
            p = subprocess.Popen(['git', 'status', '--short'],
                                 stdout=subprocess.PIPE, env=SUBPROCESS_ENV)
            out = p.communicate()[0]
            return bool(out.strip())

    def get_current_remote_fetch(self):
        with working_directory_keeper:
            os.chdir(self.target_dir)
            for line in self.log_call(['git', 'remote', '-v'],
                                      callwith=check_output).splitlines():
                if (line.endswith('(fetch)')
                        and line.startswith(BUILDOUT_ORIGIN)):
                    return line[len(BUILDOUT_ORIGIN):-7].strip()

    def offline_update(self, revision):
        target_dir = self.target_dir

        # TODO what if remote repo is actually local fs ?
        # GR, redux: git has a two notions of local repos, which
        # differ at least for shallow clones : path or file://
        if not os.path.exists(target_dir):
            # TODO case of local url ?
            raise UserError("git repository %s does not exist; cannot clone "
                            "it from %s (offline mode)" % (target_dir,
                                                           self.url))

        current_url = self.get_current_remote_fetch()
        if current_url != self.url:
            raise UserError("Existing Git repository at %r fetches from %r "
                            "which is different from the specified %r. "
                            "Cannot update adresses in offline mode." % (
                                self.target_dir, current_url, self.url))
        self.log_call(['git', 'checkout', revision],
                      callwith=update_check_call,
                      cwd=self.target_dir)

    def is_local_fixed_revision(self, refspec):
        """In Git, tags only are reproductible refspec."""
        tags = (t.strip()
                for t in self.log_call(['git', 'tag'],
                                       callwith=check_output,
                                       cwd=self.target_dir).splitlines())
        return refspec in tags

    def has_commit(self, sha):
        """Return true if repo has specified commit"""
        try:
            objtype = check_output(['git', 'cat-file', '-t', sha],
                                   cwd=self.target_dir,
                                   stderr=subprocess.PIPE).strip()
        except subprocess.CalledProcessError:
            return False

        return objtype == 'commit'

    def fetch_remote_sha(self, sha):
        """Fetch a precise SHA from remote if necessary.

        SHA pinning is suboptimal, can't be guaranteed to work (see the
        warnings emitted in code for explanations). Still, many users
        people depend on it, for not having enough privileges to add tags.
        """
        logger.warn("%s: pointing to a remote commit directly by its SHA "
                    "is unsafe because it can become unreachable "
                    "due to history rewrites (squash, rebase) in the remote "
                    "branch. "
                    "Please consider using tags if you can.", self.target_dir)
        branch = self.options.get('branch')
        if not self.has_commit(sha):
            fetch_cmd = ['git', 'fetch', BUILDOUT_ORIGIN]
            if branch is None:
                logger.info("%s: SHA pinning without remote "
                            "branch indication. "
                            "Now performing a fetch with no argument, hoping "
                            "it'll retrieve the commit %r. Please consider "
                            "adding a branch indication for more efficiency "
                            "and possibly reliability.", self.target_dir, sha)
            else:
                fetch_cmd.append(branch)
            self.log_call(fetch_cmd, callwith=update_check_call)

        self.log_call(['git', 'checkout', sha])

    def query_remote_ref(self, remote, ref):
        """Query remote repo about given ref.

        :return: ``('tag', sha)`` if ref is a tag in remote
                 ``('branch', sha)`` if ref is branch (aka "head") in remote
                 ``(None, ref)`` if ref does not exist in remote. This happens
                 notably if ref if a commit sha (they can't be queried)
        """
        out = self.log_call(['git', 'ls-remote', remote, ref],
                            cwd=self.target_dir,
                            callwith=check_output).strip()
        for sha, fullref in (l.split() for l in out.splitlines()):
            if fullref == 'refs/heads/' + ref:
                return 'branch', sha
            elif fullref == 'refs/tags/' + ref:
                return 'tag', sha
            elif fullref == ref and ref == 'HEAD':
                return 'HEAD', sha
        return None, ref

    dangerous_revisions = ('FETCH_HEAD', 'ORIG_HEAD', 'MERGE_HEAD',
                           'CHERRY_PICK_HEAD', 'REVERT_HEAD')

    def get_update(self, revision):
        """Make it so that the target directory is at the prescribed revision.

        Special case: if the 'merge' option is True,
        merge revision into current branch.
        """
        if revision in self.dangerous_revisions:
            logger.warn("%s> use of %r as revision in the recipe may "
                        "interfere with the Git subcommands issued "
                        "by the recipe in unspecified ways. It is in "
                        "particular not guaranteed to provide "
                        "consistent results on subsequent runs, new versions "
                        "of the recipe etc. "
                        "You should use them for exceptional and "
                        "timebound operations only, backed "
                        "with good knowledge of the recipe internals. "
                        "If you get a related error below, that won't be "
                        "a recipe bug.",
                        self.target_dir, revision)

        if self.options.get('merge'):
            return self.merge(revision)

        if self.offline:
            return self.offline_update(revision)

        target_dir = self.target_dir
        url = self.url

        with working_directory_keeper:
            is_new = not os.path.exists(target_dir)
            if is_new:
                self.log_call(['git', 'init', target_dir])

            os.chdir(target_dir)
            self.log_call(['git', 'remote', 'add' if is_new else 'set-url',
                           BUILDOUT_ORIGIN, url],
                          log_level=logging.DEBUG)

            rtype, sha = self.query_remote_ref(BUILDOUT_ORIGIN, revision)
            if rtype is None and ishex(revision):
                return self.fetch_remote_sha(revision)

            fetch_cmd = ['git', 'fetch']
            depth = self.options.get('depth')
            if depth is not None:
                fetch_cmd.extend(('--depth', str(depth)))
            if rtype == 'tag':
                fetch_refspec = '+refs/tags/%s:refs/tags/%s' % (revision,
                                                                revision)
            else:
                fetch_refspec = revision
            fetch_cmd.extend((BUILDOUT_ORIGIN, fetch_refspec))
            self.log_call(fetch_cmd, callwith=update_check_call)

            if rtype == 'tag':
                self.log_call(['git', 'checkout', revision])
            elif rtype in ('branch', 'HEAD'):
                self.update_fetched_branch(revision)
            else:
                raise NotImplementedError(
                    "Unknown remote reference type %r" % rtype)

    def update_fetched_branch(self, branch):
        # TODO: check what happens when there are local changes
        # TODO: what about the 'clean' option
        # setup remote tracking branch, in all cases
        # it's necessary with Git 1.7.10, not with 1.9.3 and shoud not
        # harm
        self.log_call(['git', 'update-ref', '/'.join((
            'refs', 'remotes', BUILDOUT_ORIGIN, branch)), 'FETCH_HEAD'])
        if self.options.get('depth') or branch == 'HEAD':
            # doing it the other way does not work, at least
            # not on Git 1.7
            self.log_call(['git', 'checkout', 'FETCH_HEAD'],
                          callwith=update_check_call)
            if branch != 'HEAD':
                self.log_call(['git', 'branch', '-f', branch],
                              callwith=update_check_call)
            return

        if not self._is_a_branch(branch):
            self.log_call(['git', 'checkout', '-b', branch, 'FETCH_HEAD'])
        else:
            # switch, then fast-forward
            self.log_call(['git', 'checkout', branch])
            try:
                self.log_call(['git', 'merge', '--ff-only', 'FETCH_HEAD'],
                              callwith=update_check_call)
            except UpdateError:
                if not self.clear_retry:
                    raise
                else:
                    # users are willing to wipe the entire repo
                    # to get this update done ! Let's try something less
                    # harsh first that works if previous latest commit
                    # is not an ancestor of remote latest
                    # note: fetch has already been done
                    logger.warn("Fast-forward merge failed for "
                                "repo %s, "
                                "but clear-retry option is active: "
                                "trying a reset in case that's a "
                                "simple fast-forward issue.", self)
                    self.log_call(['git', 'reset', '--hard', 'FETCH_HEAD'],
                                  callwith=update_check_call)

    def merge(self, revision):
        """Merge revision into current branch"""
        with working_directory_keeper:
            if not self.is_versioned(self.target_dir):
                raise RuntimeError("Cannot merge into non existent "
                                   "or non git local directory %s" %
                                   self.target_dir)
            os.chdir(self.target_dir)
            cmd = ['git', 'pull', self.url, revision]
            if self.git_version >= (1, 7, 10):
                # --edit and --no-edit appear with Git 1.7.10
                # see Documentation/RelNotes/1.7.10.txt of Git
                # (https://git.kernel.org/cgit/git/git.git/tree)
                cmd.insert(2, '--no-edit')

            self.log_call(cmd)

    def archive(self, target_path):
        # TODO: does this work with merge-ins?
        revision = self.parents()[0]
        if not os.path.exists(target_path):
            os.makedirs(target_path)
        with working_directory_keeper:
            os.chdir(self.target_dir)
            target_tar = tempfile.NamedTemporaryFile(
                prefix=os.path.split(self.target_dir)[1] + '.tar')
            target_tar.file.close()
            subprocess.check_call(['git', 'archive', revision,
                                   '-o', target_tar.name])
            subprocess.check_call(['tar', '-x', '-f', target_tar.name,
                                   '-C', target_path])
            os.unlink(target_tar.name)

    def revert(self, revision):
        with working_directory_keeper:
            os.chdir(self.target_dir)
            subprocess.check_call(['git', 'checkout', revision])
            if self._is_a_branch(revision):
                self.log_call(['git', 'reset', '--hard',
                              BUILDOUT_ORIGIN + '/' + revision],
                              callwith=update_check_call)
            else:
                self.log_call(['git', 'reset', '--hard', revision])

    def _is_a_branch(self, revision):
        # if this fails, we have a seriously corrupted repo
        branches = update_check_output(["git", "branch"])
        branches = branches.split()
        return revision in branches
