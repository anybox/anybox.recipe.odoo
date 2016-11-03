import os
import logging
import subprocess
import urlparse
import urllib
from StringIO import StringIO
from copy import deepcopy

from zc.buildout import UserError
from ..utils import use_or_open
from ..utils import working_directory_keeper
from ..utils import check_output
from .base import SUBPROCESS_ENV
from .base import BaseRepo
from .base import update_check_call
from .base import clone_check_call
from .base import UpdateError
from .base import CloneError

logger = logging.getLogger(__name__)

try:
    from bzrlib.plugins.launchpad.lp_directory import LaunchpadDirectory
except ImportError:
    LPDIR = None
else:
    LPDIR = LaunchpadDirectory()


class BzrBranch(BaseRepo):
    """Represent a Bazaar branch tied to a reference branch."""

    vcs_control_dir = '.bzr'

    vcs_official_name = 'Bazaar'

    def __init__(self, *a, **kw):
        super(BzrBranch, self).__init__(*a, **kw)
        if self.options.get('bzr-init') == "ligthweight-checkout":
            logger.warn("The 'ligthweight-checkout' *misspelling* is "
                        "deprecated as of version 1.7.1 of this buildout "
                        "recipe. "
                        "Please fix it as 'lightweight-checkout', as it will "
                        "probably disappear in version 1.8.")
            self.options['bzr-init'] = 'lightweight-checkout'

        if self.url.startswith('lp:') and not self.offline:
            if LPDIR is None:
                raise RuntimeError(
                    "To use launchpad locations (lp:), bzrlib must be "
                    "importable. Please also take care that it's the same "
                    "or working exactly as the one behind the bzr executable")

            # first arg (name) of look_up is acturally ignored
            url = LPDIR.look_up('', self.url)
            parsed = list(urlparse.urlparse(url))
            parsed[2] = urllib.quote(parsed[2])
            self.url = urlparse.urlunparse(parsed)

    def conf_file_path(self):
        return os.path.join(self.target_dir, '.bzr', 'branch', 'branch.conf')

    def parse_conf(self, from_file=None):
        """Return a dict of paths from standard conf (or the given file-like)

        Reference: http://doc.bazaar.canonical.com/bzr.0.18/configuration.htm

        >>> from pprint import pprint
        >>> branch = BzrBranch('', '')
        >>> pprint(branch.parse_conf(StringIO(os.linesep.join([
        ...        "parent_location = /some/path",
        ...        "submit_location = /other/path"]))))
        {'parent_location': '/some/path', 'submit_location': '/other/path'}
        """
        with use_or_open(from_file, self.conf_file_path()) as conffile:
            return dict((name.strip(), url.strip())
                        for name, url in (
                            line.split('=', 1) for line in conffile
                            if not line.startswith('#') and '=' in line))
        with working_directory_keeper:
            os.chdir(self.target_dir)

    def write_conf(self, conf, to_file=None):
        """Write counterpart to :meth:`read_conf`
        """
        lines = ('%s = %s' % (k, v) + os.linesep
                 for k, v in conf.items())
        with use_or_open(to_file, self.conf_file_path(), 'w') as conffile:
            conffile.writelines(lines)

    def update_conf(self):
        """Update branch.conf.

        :return bool: ``True`` if parent URL has changed (see lp:1320198)
        """
        try:
            conf = self.parse_conf()
        except IOError:
            logger.error("Cannot read branch.conf of Bazaar branch at %s "
                         "Proceeding anyway, remote URLs shall not be "
                         "updated if needed. Please check that the branch "
                         "is in good shape.", self.target_dir)
            return

        old_parent = conf['parent_location']
        if old_parent == self.url or self.url.startswith('lp:'):
            return False

        self.previous_conf = deepcopy(conf)
        count = 1
        while True:
            save = 'buildout_save_parent_location_%d' % count
            if save not in conf:
                conf[save] = old_parent
                break
            count += 1
        conf['parent_location'] = self.url
        self.write_conf(conf)
        return True

    def rollback_conf(self):
        """Reset branch.conf to state before latest update_conf changes.

        Only changes done through the same instance are taken into account.
        """
        previous_conf = getattr(self, 'previous_conf', None)
        if previous_conf is None:
            return

        logger.info("Rollbacking branch.conf for target %r", self.target_dir)
        self.write_conf(previous_conf)

    def uncommitted_changes(self):
        """True if we have uncommitted changes."""
        return bool(check_output(['bzr', 'status', self.target_dir],
                                 env=SUBPROCESS_ENV))

    def revision_id(self, revspec):
        """Convert revision number (revno) to globally unique revision id.

        :param str revspec: any revision specification
        :returns str: revision id specification (directly usable as -r
                      argument)
        """
        testament = check_output(['bzr', 'testament', '--strict',
                                  '-r', revspec, self.target_dir])
        prefix = 'revision-id:'
        for line in testament.splitlines():
            if line.startswith(prefix):
                return 'revid:' + line[len(prefix):].strip()

    def parents(self, as_revno=False, pip_compatible=False):
        """Return current revision.

        :param as_revno: if ``True``, the revno will be returned. By default,
                         a full revision id is issued (see :meth:`revision_id`)
        :param pip_compatible: currently, setting this to ``True`` forces
                               ``as_revno`` to ``True`` (pip URL syntax for bzr
                               does not allow revids, because of the ``@`` in
                               bzr revids)

        This method will not detect pending merges, but
        :meth:`uncommitted_changes` will, and that is enough for freeze/extract
        features.
        """
        revno = check_output(['bzr', 'revno', '--tree', self.target_dir],
                             env=SUBPROCESS_ENV).strip()
        if pip_compatible:
            as_revno = True
        if as_revno:
            return [revno]

        return [self.revision_id(revno)]

    def clean(self):
        if not os.path.exists(self.target_dir):
            # not branched yet, there's nothing to clean
            return
            subprocess.check_call(['bzr', 'clean-tree',
                                   '--ignored', '--force'])
        with working_directory_keeper:
            os.chdir(self.target_dir)
            subprocess.check_call(['bzr', 'clean-tree',
                                   '--ignored', '--force'])

    def revert(self, revision):
        logger.info("Reverting bzr repo at %s to revision %r", self.target_dir,
                    revision)
        with working_directory_keeper:
            os.chdir(self.target_dir)
            subprocess.check_call(['bzr', 'revert', '-r', revision])

    def _update(self, revision):
        """Update existing branch at target dir to given revision.

        raise UpdateError in case of problems."""

        update_check_call(['bzr', 'up', '-r', revision, self.target_dir],
                          env=SUBPROCESS_ENV)
        logger.info("Updated %r to revision %s", self.target_dir, revision)

    def get_revid(self, revision):
        """Convert a locally available revision to a revid.

        :param str revision: any valid revision string.
        :raises: :class:`LookupError` if not actually available.
        """
        with working_directory_keeper:
            os.chdir(self.target_dir)
            try:
                log = check_output(
                    ['bzr', 'log', '--show-ids', '-r', revision],
                    env=SUBPROCESS_ENV)
            except subprocess.CalledProcessError as exc:
                if exc.returncode != 3:
                    raise
                raise LookupError(
                    "could not find revision id for %r" % revision)

            prefix = 'revision-id:'
            for line in log.split(os.linesep):
                if line.startswith(prefix):
                    return line[len(prefix):].strip()
            raise LookupError("could not find revision id for %r" % revision)

    def is_revno(self, revspec, fixed=False):
        """True iff revspec is a fixed revision number.

        Valid revision numbers are integers separated by dots.

        :param fixed: if ``True``, it is further checked that integers
                      are positive.
        """

        revno_prefix = 'revno:'
        if revspec.startswith(revno_prefix):
            # GR I checked on Debian's 2.6.0~bzr6526-1, revno:-1
            # is in practice accepted by bzr, so we have to check
            return self.is_revno(revspec[len(revno_prefix):])

        for part in revspec.strip().split('.'):
            try:
                part = int(part)
            except ValueError:
                return False
            else:
                if fixed and part <= 0:
                    return False

        return True

    def is_fixed_revision(self, revstr):
        """True iff the given revision string is for a fixed revision."""

        revstr = revstr.strip()  # one never knows
        if revstr.startswith('revid:') or revstr.startswith('tag:'):
            return True
        if not revstr or revstr.startswith('last:'):
            return False
        if self.is_revno(revstr, fixed=True):
            return True

    def is_local_fixed_revision(self, revstr):
        if not self.is_fixed_revision(revstr):
            return False
        try:
            self.get_revid(revstr)
        except LookupError:
            return False
        else:
            return True

    def get_update(self, revision):
        """Ensure that target_dir is a branch of url at specified revision.

        If target_dir already exists, does a simple pull.
        Offline-mode: no branch nor pull, but update.
        In all cases, an attempt to update is performed before any pull

        Special case: if the 'merge' option is True,
        merge revision into current branch.
        """
        target_dir = self.target_dir
        offline = self.offline
        clear_locks = self.clear_locks

        if not os.path.exists(target_dir) or \
                self.options.get("bzr-init") == 'merge':
            try:
                self._branch(revision)
            except CloneError:
                if not revision:
                    raise
                logger.warning("First attempt of branching to %s at revision "
                               "%r failed. Retrying in two steps.", target_dir,
                               revision)
                # it really happens, see
                # https://bugs.launchpad.net/anybox.recipe.openerp/+bug/1204573
                self._branch(None)
                self._update(revision)

        else:
            # TODO what if bzr source is actually local fs ?
            if clear_locks:
                yes = StringIO()
                yes.write('y')
                yes.seek(0)
                logger.info("Break-lock for branch %s ...", target_dir)
                # GR newer versions of bzr have a --force option, but this call
                # works also for older ones (fortunately we don't need a pty)
                p = subprocess.Popen(['bzr', 'break-lock', target_dir],
                                     subprocess.PIPE)
                out, err = p.communicate(input='y')
                if p.returncode != 0:
                    raise subprocess.CalledProcessError(
                        p.returncode, repr(['bzr', 'break-lock', target_dir]))

            parent_changed = self.update_conf()
            unsafe_revno = parent_changed and self.is_revno(revision)
            fixed_rev = self.is_fixed_revision(revision)

            init_opt = self.options.get('bzr-init')

            if fixed_rev and not unsafe_revno:
                if (offline and init_opt == 'lightweight-checkout'):
                    logger.warning("Offline mode, no update for lightweight "
                                   "checkout at %s on revision %r",
                                   self.target_dir, revision)
                    return
                try:
                    self._update(revision)
                    return
                except UpdateError:
                    if offline:
                        raise

            if offline:
                if parent_changed and (unsafe_revno or not fixed_rev):
                    self.rollback_conf()
                    raise UserError(
                        "Change of parent URL with live or revno revision "
                        "specification: %r is forbidden in offline mode. "
                        "If that revno is common to old and new remote "
                        "branch, consider using revision IDs "
                        "instead." % revision)

                logger.info("Offline mode, no pull for revision %r", revision)
            else:
                self._pull()

            if not (offline and init_opt in ('stacked-branch',
                                             'lightweight-checkout')):
                self._update(revision)

    def _branch(self, revision):
        """ Branch or checkout remote repository
        """
        target_dir = self.target_dir
        url = self.url
        offline = self.offline
        # TODO case of local url ?
        if offline:
            raise IOError(
                "bzr branch %s does not exist; cannot branch it from "
                "%s (offline mode)" % (target_dir, url))

        options = self.options
        if "bzr-init" in options and "bzr-stacked-branches" in options:
            raise Exception(
                "Both options 'bzr-init' and "
                "'bzr-stacked-branches' are mutually exclusive. "
                "Prefer 'bzr-init'.")
        default = "branch"

        if "bzr-stacked-branches" in options:
            logger.warning("'bzr-stacked-branches' option is deprecated. "
                           "Replace by bzr-init=stacked-branch")
            default = "stacked-branch"

        bzr_opt = options.get("bzr-init", default)
        branch_cmd = ['bzr']
        if bzr_opt == "branch":
            branch_cmd.append("branch")
            logger.info("Branching %s ...", url)
        elif bzr_opt == "stacked-branch":
            branch_cmd.extend(["branch", "--stacked"])
            logger.info("Stacked branching %s ...", url)
        elif bzr_opt == "lightweight-checkout":
            branch_cmd.extend(["checkout", "--lightweight"])
            logger.info("Lightweight checkout %s ...", url)
        elif bzr_opt == "merge":
            branch_cmd.extend(["merge", "--force"])
            logger.info("Merging %s into %s ...", url, self.target_dir)
        else:
            raise Exception("Unsupported option %r" % bzr_opt)

        if revision:
            branch_cmd.extend(['-r', revision])
        if bzr_opt == "merge":
            branch_cmd.extend([url, '-d', target_dir])
        else:
            branch_cmd.extend([url, target_dir])

        clone_check_call(branch_cmd, env=SUBPROCESS_ENV)

    def _pull(self):
        if self.options.get('bzr-init') == 'lightweight-checkout':
            logger.info("Update lightweight checkout at %s ...",
                        self.target_dir)
            update_check_call(['bzr', 'update', self.target_dir],
                              env=SUBPROCESS_ENV)
        else:
            logger.info("Pull for branch %s ...", self.target_dir)
            update_check_call(['bzr', 'pull', '-d', self.target_dir],
                              env=SUBPROCESS_ENV)

    def archive(self, target_path):
        with working_directory_keeper:
            os.chdir(self.target_dir)
            subprocess.check_call(['bzr', 'export', target_path])
