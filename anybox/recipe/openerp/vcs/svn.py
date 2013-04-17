import os
import subprocess
import logging

from ..utils import working_directory_keeper
from .base import BaseRepo

logger = logging.getLogger(__name__)


class SvnCheckout(BaseRepo):

    vcs_control_dir = '.svn'

    def get_update(self, revision):
        """Ensure that target_dir is a branch of url at specified revision.

        If target_dir already exists, does a simple pull.
        Offline-mode: no branch nor pull, but update.
        """
        target_dir = self.target_dir
        url = self.url
        offline = self.offline

        rev_str = revision and '-r ' + revision or ''

        with working_directory_keeper:
            if not os.path.exists(target_dir):
                # TODO case of local url ?
                if offline:
                    raise IOError(
                        "svn checkout %s does not exist; cannot checkout "
                        "from %s (offline mode)" % (target_dir, url))

                os.chdir(os.path.split(target_dir)[0])
                logger.info("Checkouting %s ...", url)
                subprocess.check_call('svn checkout %s %s %s' % (
                    rev_str, url, target_dir), shell=True)
            else:
                os.chdir(target_dir)
                # TODO what if remote repo is actually local fs ?
                if offline:
                    logger.warning(
                        "Offline mode: keeping checkout %s in its current rev",
                        target_dir)
                else:
                    logger.info("Updating %s to location %s, revision %s...",
                                target_dir, url, revision)
                    # switch is necessary in order to move in tags
                    # TODO support also change of svn root url
                    subprocess.check_call('svn switch %s' % url, shell=True)
                    subprocess.check_call('svn up %s' % rev_str,
                                          shell=True)
