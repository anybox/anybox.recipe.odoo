import os
import shutil
import subprocess

SUBPROCESS_ENV = os.environ.copy()
SUBPROCESS_ENV['PYTHONPATH'] = SUBPROCESS_ENV.pop(
    'BUILDOUT_ORIGINAL_PYTHONPATH', '')


class UpdateError(subprocess.CalledProcessError):
    """Specific class for errors occurring during updates of existing repos.
    """


def update_check_call(*args, **kwargs):
    """Variant on subprocess.check_call that raises UpdateError."""
    try:
        subprocess.check_call(*args, **kwargs)
    except subprocess.CalledProcessError, e:
        raise UpdateError(e.returncode, e.cmd)


class BaseRepo(object):

    def __init__(self, target_dir, url, clear_retry=False,
                 offline=False, clear_locks=False, **options):

        self.target_dir = target_dir
        self.url = url
        self.clear_retry = clear_retry
        self.offline = offline
        self.clear_locks = clear_locks

        # additional options that may depend on the VCS subclass
        self.options = options

    def clear_target(self):
        shutil.rmtree(self.target_dir)

    def __call__(self, revision):
        try:
            self.get_update(revision)
        except UpdateError:
            if self.offline or not self.clear_retry:
                raise
            self.clear_target()
            self.get_update(revision)

    @classmethod
    def is_versioned(cls, path):
        """True if path exists and is versioned under this vcs.

        Common implementation based on vcs_control_dir class attribute.
        """
        return os.path.exists(os.path.join(path, cls.vcs_control_dir))

    @classmethod
    def fix_target(cls, target_dir):
        """Take into account that some targets are actually shifted below.

        That is the case of standalon addon (see launchpad #1012899).
        """

        if os.path.exists(target_dir) and not cls.is_versioned(target_dir):
            name = os.path.split(target_dir)[-1]
            new_target = os.path.join(target_dir, name)
            manifest = os.path.join(new_target, '__openerp__.py')
            if cls.is_versioned(new_target) and os.path.exists(manifest):
                return new_target
        return target_dir

    def uncommitted_changes(self):
        """True if we have uncommitted changes."""
        raise NotImplementedError

    def parents(self):
        """Return universal identifier for parent nodes, aka current revisions.

        There might be more than one with some VCSes (ex: pending merge in hg).
        """
        raise NotImplementedError
