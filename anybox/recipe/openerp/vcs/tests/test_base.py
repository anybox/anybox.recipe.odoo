"""Test VCS methods (common part).

These tests depend on system executables, such as 'hg', 'bzr', etc.
"""

import os
import subprocess

from .. import get_update
from .. import testing
from .. import SUPPORTED
from ..base import UpdateError
from ..hg import HgRepo


class CommonTestCase(testing.VcsTestCase):
    """Test methods that are common among the different repository classes."""

    def create_src(self):
        """We use HgRepo to test the common features."""

        os.chdir(self.src_dir)
        subprocess.call(['hg', 'init', 'src-repo'])
        self.src_repo = os.path.join(self.src_dir, 'src-repo')
        os.chdir('src-repo')
        f = open('tracked', 'w')
        f.write("default" + os.linesep)
        f.close()
        subprocess.call(['hg', 'add'])
        subprocess.call(['hg', 'commit', '-m', 'initial commit',
                         '-u', testing.COMMIT_USER_FULL])

    def test_unknown(self):
        self.assertRaises(ValueError,
                          get_update, 'unknown', '', '', 'default')

    def test_retry(self):
        """With a repo class that fails updates, retry works."""

        class HgRepoFailsUpdates(HgRepo):
            def get_update(self, revision):
                if os.path.exists(self.target_dir):
                    raise UpdateError(1, ['error'])
                HgRepo.get_update(self, revision)

        SUPPORTED['hg_fails_updates'] = HgRepoFailsUpdates
        repo_path = os.path.join(self.dst_dir, "clone")

        get_update('hg_fails_updates', repo_path, self.src_repo, 'default')
        self.assertTrue(os.path.isdir(repo_path))

        # without the retry option
        self.assertRaises(UpdateError, get_update, 'hg_fails_updates',
                          repo_path, self.src_repo, 'default')

        # now the retry
        get_update('hg_fails_updates', repo_path, self.src_repo, 'default',
                   clear_retry=True)

        # no such wild retry in offline mode
        self.assertRaises(UpdateError, get_update, 'hg_fails_updates',
                          repo_path, self.src_repo, 'default', offline=True)
