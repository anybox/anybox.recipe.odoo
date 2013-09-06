import os
import sys
import subprocess
import logging
import tempfile

from ..utils import working_directory_keeper
from .base import BaseRepo
from .base import SUBPROCESS_ENV
from anybox.recipe.openerp import utils
import re

logger = logging.getLogger(__name__)


class GitRepo(BaseRepo):
    """Represent a Git clone tied to a reference branch."""

    vcs_control_dir = '.git'

    def clean(self):
        if not os.path.isdir(self.target_dir):
            return
        with working_directory_keeper:
            os.chdir(self.target_dir)
            subprocess.check_call(['git', 'clean', '-fdqx'])

    def parents(self):
        """Return full hash of parent nodes. """
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
        rev_str = revision

        with working_directory_keeper:
            is_target_dir_exists = os.path.exists(target_dir)
            if not is_target_dir_exists:
                # TODO case of local url ?
                if offline:
                    raise IOError(
                        "git repository %s does not exist; cannot clone it "
                        "from %s (offline mode)" % (target_dir, url))

                os.chdir(os.path.split(target_dir)[0])
                logger.info("Cloning %s ...", url)
                subprocess.check_call(['git', 'clone', url, target_dir])
            os.chdir(target_dir)

            if is_target_dir_exists:
                # TODO what if remote repo is actually local fs ?
                if not offline:
                    logger.info("Fetch for git repo %s (rev %s)...",
                                target_dir, rev_str)
                    subprocess.check_call(['git', 'fetch'])

            if revision and self._needToSwitchRevision(revision):
                # switch to the expected revision
                logger.info("Checkout %s to revision %s",
                            target_dir, revision)
                self._switch(revision)

    def archive(self, target_path):
        revision = self.parents()[0]
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

    def _needToSwitchRevision(self, revision):
        """ Check if we need to checkout to an other branch
        """
        p = utils.check_output(['git', 'rev-parse', '--abbrev-ref', 'HEAD'])
        rev = p.split()[0]  # remove \n
        logger.info("Current revision '%s' - Expected revision '%s'",
                    rev, revision)
        return rev != revision

    def _switch(self, revision):
        rbp = self._remote_branch_prefix
        branches = utils.check_output(["git", "branch", "-a"])
        branch = revision
        if re.search("^(\*| ) %s$" % re.escape(branch), branches, re.M):
            # the branch is local, normal checkout will work
            logger.info("The branch is local; normal checkout ")
            argv = ["checkout", branch]
        elif re.search(
            "^  " + re.escape(rbp) + "\/" + re.escape(branch) + "$", branches,
                re.M):
            # the branch is not local, normal checkout won't work here
            logger.info("The branch is not local; checkout remote branch ")
            argv = ["checkout", "-b", branch, "%s/%s" % (rbp, branch)]
        else:
            # A tag or revision was specified instead of a branch
            logger.info("Checkout tag or revision")
            argv = ["checkout", revision]
        # runs the checkout with predetermined arguments
        argv.insert(0, "git")
        subprocess.check_call(argv)

    @property
    def _remote_branch_prefix(self):
        version = self._git_version
        if version < (1, 6, 3):
            return "origin"
        else:
            return "remotes/origin"

    @property
    def _git_version(self):
        out = utils.check_output(["git", "--version"])
        m = re.search("git version (\d+)\.(\d+)(\.\d+)?(\.\d+)?", out)
        if m is None:
            logger.error("Unable to parse git version output")
            logger.error("'git --version' output was:\n%s\n%s", out)
            sys.exit(1)
        version = m.groups()

        if version[3] is not None:
            version = (
                int(version[0]),
                int(version[1]),
                int(version[2][1:]),
                int(version[3][1:])
            )
        elif version[2] is not None:
            version = (
                int(version[0]),
                int(version[1]),
                int(version[2][1:])
            )
        else:
            version = (int(version[0]), int(version[1]))
        if version < (1, 5):
            logger.error(
                "Git version %s is unsupported, please upgrade",
                ".".join([str(v) for v in version]))
            sys.exit(1)
        return version
