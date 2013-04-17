import os
import subprocess
import logging

from ..utils import working_directory_keeper
from .base import BaseRepo

logger = logging.getLogger(__name__)


class GitRepo(BaseRepo):
    """Represent a Git clone tied to a reference branch."""

    vcs_control_dir = '.git'

    def get_update(self, revision):
        """Ensure that target_dir is a branch of url at specified revision.

        If target_dir already exists, does a simple pull.
        Offline-mode: no branch nor pull, but update.
        """
        target_dir = self.target_dir
        url = self.url
        offline = self.offline
        rev_str = revision

        with working_directory_keeper:
            if not os.path.exists(target_dir):
                # TODO case of local url ?
                if offline:
                    raise IOError(
                        "git repository %s does not exist; cannot clone it "
                        "from %s (offline mode)" % (target_dir, url))

                os.chdir(os.path.split(target_dir)[0])
                logger.info("Cloning %s ...", url)
                subprocess.check_call(['git', 'clone', '-b',
                                       rev_str, url, target_dir])
            else:
                os.chdir(target_dir)
                # TODO what if remote repo is actually local fs ?
                if not offline:
                    logger.info("Pull for git repo %s (rev %s)...",
                                target_dir, rev_str)
                    subprocess.check_call(['git', 'pull',
                                          url, rev_str])
                elif revision:
                    logger.info("Checkout %s to revision %s",
                                target_dir, revision)
                    subprocess.check_call(['git', 'checkout', rev_str])
