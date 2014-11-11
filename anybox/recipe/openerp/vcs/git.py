import os
import subprocess
import logging
import tempfile

from ..utils import working_directory_keeper
from .base import BaseRepo
from .base import SUBPROCESS_ENV
from .base import update_check_call
from .base import update_check_output
from .base import UpdateError
from anybox.recipe.openerp import utils

logger = logging.getLogger(__name__)

BUILDOUT_ORIGIN = 'origin'


class GitRepo(BaseRepo):
    """Represent a Git clone tied to a reference branch/commit/tag."""

    vcs_control_dir = '.git'

    vcs_official_name = 'Git'

    _git_version = None

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

        Expected exceptions:

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
            callwith(cmd, **kw)

    def clean(self):
        if not os.path.isdir(self.target_dir):
            return
        with working_directory_keeper:
            os.chdir(self.target_dir)
            subprocess.check_call(['git', 'clean', '-fdqx'])

    def parents(self, pip_compatible=False):
        """Return full hash of parent nodes.

        :param pip_compatible: ignored, all Git revspecs are pip compatible
        """
        with working_directory_keeper:
            os.chdir(self.target_dir)
            p = subprocess.Popen(['git', 'rev-parse', '--verify', 'HEAD'],
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

    def get_update(self, revision):
        """Make it so that the target directory is at the prescribed revision.

        Special case: if the 'merge' option is True,
        merge revision into current branch.
        """
        if self.options.get('merge'):
            return self.merge(revision)

        target_dir = self.target_dir
        url = self.url
        offline = self.offline

        with working_directory_keeper:
            if not os.path.exists(target_dir):
                if offline:
                    # TODO case of local url ?
                    raise IOError(
                        "git repository %s does not exist; cannot clone "
                        "it from %s (offline mode)" % (target_dir, url))
                self.log_call(['git', 'init', target_dir])
                os.chdir(target_dir)
                self.log_call(['git', 'remote', 'add',
                               BUILDOUT_ORIGIN, url])

            if not offline:
                # TODO what if remote repo is actually local fs ?
                # GR, redux: git has a two notions of local repos, which
                # differ at least for shallow clones : path or file://
                os.chdir(target_dir)
                self.log_call(
                    ['git', 'remote', 'set-url', BUILDOUT_ORIGIN, url],
                    callwith=subprocess.call)
                self.log_call(['git', 'fetch', BUILDOUT_ORIGIN])
                # TODO: check what happens when there are local changes
                # TODO: what about the 'clean' option
                self.log_call(['git', 'checkout', revision])
                if self._is_a_branch(revision):
                    # fast forward
                    try:
                        self.log_call(['git', 'merge', '--ff-only',
                                       BUILDOUT_ORIGIN + '/' + revision],
                                      callwith=update_check_call)
                    except UpdateError:
                        if not self.clear_retry:
                            raise
                        else:
                            # users are willing to wipe the entire repo
                            # to get their updates ! Let's try something less
                            # harsh first that works if previous latest commit
                            # is not an ancestor of remote latest
                            # note: fetch has already been done
                            logger.warn("Fast-forward merge failed for "
                                        "repo %s, "
                                        "but clear-retry option is active: "
                                        "trying a reset in case that's a "
                                        "simple fast-forward issue.", self)
                            self.log_call(['git', 'reset', '--hard',
                                           'origin/%s' % revision],
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
            if self.git_version >= (1, 7, 8):
                # --edit and --no-edit appear with Git 1.7.8
                # see Documentation/RelNotes/1.7.8.txt of Git
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
                              BUILDOUT_ORIGIN + '/' + revision])
            else:
                self.log_call(['git', 'reset', '--hard', revision])

    def _is_a_branch(self, revision):
        # if this fails, we have a seriously corrupted repo
        branches = update_check_output(["git", "branch"])
        branches = branches.split()
        return revision in branches
