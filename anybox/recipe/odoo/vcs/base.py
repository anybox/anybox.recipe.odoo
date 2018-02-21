import os
import shutil
import subprocess
import logging
from .. import utils

SUBPROCESS_ENV = os.environ.copy()
SUBPROCESS_ENV['PYTHONPATH'] = SUBPROCESS_ENV.pop(
    'BUILDOUT_ORIGINAL_PYTHONPATH', '')

logger = logging.getLogger(__name__)


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
        except subprocess.CalledProcessError as e:
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
    """The common interface that all repository classes implement.

    :param target_dir: the local directory which will serve as a working tree
    :param offline: if ``True``, the repository instance will perform no
                    network operation, and will fail instead if a non
                    available revision is required.
    :param clear_locks: Some VCS systems can leave locks after some failures
                        and provide a separate way to break them. If ``True``,
                        the repo
                        will break any locks prior to operations (mostly useful
                        for automated agents, such as CI robots)
    :param clear_retry: if ``True`` failed updates by calling the instance are
                        cleared (see :meth:`clear_target`) and retried once.
                        This is intended for brittle VCSes from CI robots.

    Other options depend on the concrete repository class.

    Repository instances are **callable**. For each of them::

        repo(rev)

    will take all the steps necessary so that its local directory is a clone of
    the remote source, at the specified revision. If needed and possible
    The revision format depends on the
    concrete class, but it is passed as a :class:`str`.
    """

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
        """Entirely remove the target directory."""
        shutil.rmtree(self.target_dir)

    def clean(self):
        """Remove unwanted untracked files.

        This default implementation removes Python object files and
        (resulting) empty directories.
        Subclasses are supposed to implement better vcs-specific behaviours.
        It is important for release-related options that this cleaning does not
        appear as a local modification.
        """
        utils.clean_object_files(self.target_dir)

    def revert(self, revision):
        """Revert any local changes, including pending merges."""
        raise NotImplementedError

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
            logger.warn("Update of %s failed, removing and re-cloning "
                        "according to the clear-retry option. ", self)
            self.clear_target()
            self.get_update(revision)
        return self  # nicer in particular for tests

    def get_update(self, revision):
        """Make it so that the target directory is at the prescribed revision.

        The target directory need not to be initialized: this method will
        "clone" it from the remote source (whatever that means in the
        considered VCS).

        This method can fail under various circumstances, for instance if the
        wanted revision does not exist locally and offline mode has been
        selected.

        :raises CloneError: if initial cloning fails
        :raises UpdateError: if update of existing repository fails

        Must be implemented in concrete subclasses
        """
        raise NotImplementedError

    def __str__(self):
        return "%s at %r (remote=%r)" % (
            self.__class__.__name__, self.target_dir, self.url)

    @classmethod
    def is_versioned(cls, path):
        """True if path exists and is versioned under this vcs.

        Common implementation based on vcs_control_dir class attribute.
        """
        return os.path.exists(os.path.join(path, cls.vcs_control_dir))

    def uncommitted_changes(self):
        """True if we have uncommitted changes.

        Must be implemented by concrete subclasses
        """
        raise NotImplementedError

    def is_local_fixed_revision(self, revspec):
        """True if revspec is a locally available fixed revision.

        The concept of a fixed revision depends on the concrete VCS in use.
        It means that retrieving revspec at any point in the future

        1. is guaranteed to work
        2. always yields the same result

        In practice, for most VCSes, these cannot be totally guaranteed, but
        each VCS defines those cases whose breaking is considered to be a
        very bad practice.

        In Mercurial, removing a commit from a public repository is possible,
        but very bad.
        In Git, removing a commit from a public repository is normal workflow,
        but removing a tag is very bad.

        The name stresses that only locally available ones will be recognized
        due to the promise that this method does not query any remote repo.
        """
        raise NotImplementedError

    def parents(self, pip_compatible=False):
        """Return universal identifier for parent nodes, aka current revisions.

        There might be more than one with some VCSes (ex: pending merge in hg).

        :param pip_compatible: if ``True``, only `pip compatible
                               <http://pip.readthedocs.org/en/latest/
                               reference/pip_install.html#vcs-support>`_
                               revision specifications are returned, depending
                               on the VCS type.
        """
        raise NotImplementedError

    def archive(self, target_path):
        raise NotImplementedError
