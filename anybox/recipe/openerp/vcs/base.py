import os
import shutil
import subprocess
from .. import utils

SUBPROCESS_ENV = os.environ.copy()
SUBPROCESS_ENV['PYTHONPATH'] = SUBPROCESS_ENV.pop(
    'BUILDOUT_ORIGINAL_PYTHONPATH', '')


class UpdateError(subprocess.CalledProcessError):
    """Specific class for errors occurring during updates of existing repos.
    """


class CloneError(subprocess.CalledProcessError):
    """Class to easily signal errors in initial cloning.
    """


def wrap_check_call(exc_cls, call_fn):

    def wrapped_check_call(*args, **kwargs):
        """Variant on subprocess.check_* that raises %s.""" % exc_cls
        try:
            return call_fn(*args, **kwargs)
        except subprocess.CalledProcessError, e:
            up_exc = exc_cls(e.returncode, e.cmd)
            output = getattr(e, 'output', None)
            if output is not None:
                up_exc.output = output
            raise up_exc

    return wrapped_check_call

update_check_call = wrap_check_call(UpdateError, subprocess.check_call)
clone_check_call = wrap_check_call(CloneError, subprocess.check_call)
update_check_output = wrap_check_call(UpdateError, utils.check_output)
clone_check_output = wrap_check_call(CloneError, utils.check_output)


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

    def clean(self):
        """Remove unwanted untracked files.

        The default implementation removes Python object files and
        (resulting) empty directories.
        Subclasses are supposed to implement better vcs-specific behaviours.
        It is important for release-related options that this cleaning does not
        appear as a local modification.
        """
        utils.clean_object_files(self.target_dir)

    def __call__(self, revision):
        """Create if needed from remote source, and put it at wanted revision.
        """
        if self.options.get('clean'):
            self.clean()

        try:
            self.get_update(revision)
        except UpdateError:
            if self.offline or not self.clear_retry:
                raise
            self.clear_target()
            self.get_update(revision)
        return self  # nicer in particular for tests

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
            manifest2 = os.path.join(new_target, '__terp__.py')
            exists = os.path.exists(manifest)
            exists = exists or os.path.exists(manifest2)
            if cls.is_versioned(new_target) and exists:
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
