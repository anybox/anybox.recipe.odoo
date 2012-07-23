"""Utilities for unit tests."""
import os
from anybox.recipe.openerp import vcs

class FakeRepo(vcs.BaseRepo):

    log = []

    log_std_options = True

    vcs_control_dir = '.fake'

    def get_update(self, revision):
        if not os.path.isdir(self.target_dir):
            os.mkdir(self.target_dir)
        control = os.path.join(self.target_dir, self.vcs_control_dir)
        if not os.path.isdir(control):
            os.mkdir(control)

        options = self.options.copy()
        if self.log_std_options:
            options['offline'] = self.offline
            options['clear_locks'] = self.clear_locks
        self.log.append((self.target_dir, self.url, revision, options),)

vcs.SUPPORTED['fakevcs'] = FakeRepo

def get_vcs_log():
    return FakeRepo.log

def clear_vcs_log():
    FakeRepo.log = []

