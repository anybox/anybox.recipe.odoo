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
    """Represent a Git clone tied to a reference branch."""

    vcs_control_dir = '.git'

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
        """Ensure that target_dir is a branch of url at specified revision.

        If target_dir already exists, does a simple fetch.
        Offline-mode: no branch nor fetch, but checkout.
        """
        target_dir = self.target_dir
        url = self.url
        offline = self.offline

        with working_directory_keeper:
            if not self.options.get('merge'):
                if not os.path.exists(target_dir):
                    # TODO case of local url ?
                    if offline:
                        raise IOError(
                            "git repository %s does not exist; cannot clone "
                            "it from %s (offline mode)" % (target_dir, url))
                    print("-> git init %s" % (target_dir,))
                    subprocess.check_call(['git', 'init', target_dir])
                    os.chdir(target_dir)
                    print("-> git remote add %s %s" %
                          (BUILDOUT_ORIGIN, url))
                    subprocess.check_call(['git', 'remote', 'add',
                                           BUILDOUT_ORIGIN, url])

                # TODO what if remote repo is actually local fs ?
                os.chdir(target_dir)
                if not offline:
                    print("-> remote set-url %s %s" %
                          (BUILDOUT_ORIGIN, url))
                    subprocess.call(['git', 'remote', 'set-url',
                                     BUILDOUT_ORIGIN, url])
                    print("-> fetch %s into %s" %
                          (BUILDOUT_ORIGIN, target_dir))
                    subprocess.check_call(['git', 'fetch', BUILDOUT_ORIGIN])
                    # TODO: check what happens when there are local changes
                    # TODO: what about the 'clean' option
                    print("-> checkout %s" % (revision,))
                    subprocess.check_call(['git', 'checkout', revision])
                    if self._is_a_branch(revision):
                        # fast forward
                        print("-> merge %s/%s" % (BUILDOUT_ORIGIN, revision,))
                        subprocess.check_call(['git', 'merge',
                                               BUILDOUT_ORIGIN + '/' + revision])
            else:
                if not self.is_versioned(target_dir):
                    raise RuntimeError("Cannot merge into non existent "
                                       "or non git local directory %s" %
                                       target_dir)
                os.chdir(target_dir)
                print("pull %s %s into %s" %
                      (url, revision, target_dir))
                subprocess.check_call(['git', 'pull', '--no-edit',
                                       url, revision])

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
        for branch in branches.split("\n"):
            branch = branch[2:]
            if revision == branch:
                return True
        return False
