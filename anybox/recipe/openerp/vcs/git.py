import os
import subprocess
import logging
import tempfile

from ..utils import working_directory_keeper
from .base import BaseRepo
from .base import SUBPROCESS_ENV
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

        return cls.init_git_version(subprocess.check_output(
            ['git', '--version']))

    @classmethod
    def init_git_version(cls, v_str):
        """Parse git version string and store the resulting tuple on self.

        :returns: the parsed version tuple

        Some real-life examples::

          >>> GitRepo.init_git_version('git version 1.8.5.3')
          (1, 8, 5, 3)
          >>> GitRepo.init_git_version('git version 1.7.2.5')
          (1, 7, 2, 5)

        This one does not exist, allowing us to prove that this method
        actually governs the :attr:`git_version` property

          >>> GitRepo.init_git_version('git version 1.6.6.6')
          (1, 6, 6, 6)
          >>> GitRepo('', '').git_version
          (1, 6, 6, 6)

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
                int(x) for x in v_str.split('git version ', 1)[-1].split('.'))
        except:
            raise ValueError("Could not parse git version output %r. Please "
                             "report this" % v_str)
        return version

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
                logger.info("%s> git init", target_dir)
                subprocess.check_call(['git', 'init', target_dir])
                os.chdir(target_dir)
                logger.info("%s> git remote add %s %s",
                            target_dir, BUILDOUT_ORIGIN, url)
                subprocess.check_call(['git', 'remote', 'add',
                                       BUILDOUT_ORIGIN, url])

            if not offline:
                # TODO what if remote repo is actually local fs ?
                # GR, redux: git has a two notions of local repos, which
                # differ at least for shallow clones : path or file://
                os.chdir(target_dir)
                logger.info("%s> git remote set-url %s %s",
                            target_dir, BUILDOUT_ORIGIN, url)
                subprocess.call(['git', 'remote', 'set-url',
                                 BUILDOUT_ORIGIN, url])
                logger.info("%s> git fetch %s",
                            target_dir, BUILDOUT_ORIGIN)
                subprocess.check_call(['git', 'fetch', BUILDOUT_ORIGIN])
                # TODO: check what happens when there are local changes
                # TODO: what about the 'clean' option
                logger.info("%s> git checkout %s", target_dir, revision)
                subprocess.check_call(['git', 'checkout', revision])
                if self._is_a_branch(revision):
                    # fast forward
                    logger.info("%s> git merge %s/%s",
                                target_dir, BUILDOUT_ORIGIN, revision)
                    subprocess.check_call(['git', 'merge',
                                           BUILDOUT_ORIGIN + '/' + revision])

    def merge(self, revision):
        """Merge revision into current branch"""
        with working_directory_keeper:
            if not self.is_versioned(self.target_dir):
                raise RuntimeError("Cannot merge into non existent "
                                   "or non git local directory %s" %
                                   self.target_dir)
            os.chdir(self.target_dir)
            logger.info("%s> git pull %s %s",
                        self.target_dir, self.url, revision)
            cmd = ['git', 'pull', self.url, revision]
            if self.git_version >= (1, 7, 8):
                # --edit and --no-edit appear with Git 1.7.8
                # see Documentation/RelNotes/1.7.8.txt of Git
                # (https://git.kernel.org/cgit/git/git.git/tree)
                cmd.insert(2, '--no-edit')

            subprocess.check_call(cmd)

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
                subprocess.check_call(['git', 'reset', '--hard',
                                       BUILDOUT_ORIGIN + '/' + revision])
            else:
                subprocess.check_call(['git', 'reset', '--hard', revision])

    def _is_a_branch(self, revision):
        branches = utils.check_output(["git", "branch"])
        branches = branches.split()
        return revision in branches
