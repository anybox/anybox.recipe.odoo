import os
import logging
import subprocess
import urlparse
import urllib
from StringIO import StringIO

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

    def __init__(self, *a, **kw):
        super(BzrBranch, self).__init__(*a, **kw)
        if self.options.get('bzr-init') == "ligthweight-checkout":
            logger.warn("The 'ligthweight-checkout' *misspelling* is "
                        "deprecated as of version 1.7.1 of this buildout "
                        "recipe. "
                        "Please fix it as 'lightweight-checkout', as it will "
                        "probably disappear in version 1.8.")
            self.options['bzr-init'] = 'lightweight-checkout'

        if self.url.startswith('lp:'):
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

    def write_conf(self, conf, to_file=None):
        """Write counterpart to read_conf (see docstring of read_conf)
        """
        lines = ('%s = %s' % (k, v) + os.linesep
                 for k, v in conf.items())
        with use_or_open(to_file, self.conf_file_path(), 'w') as conffile:
            conffile.writelines(lines)

    def update_conf(self):
        try:
            conf = self.parse_conf()
        except IOError:
            logger.error("Cannot read branch.conf of Bazaar branch at %s "
                         "Proceeding anyway, remote URLs shall not be "
                         "updated if needed. Please check that the branch "
                         "is in good shape.", self.target_dir)
            return

        old_parent = conf['parent_location']
        if old_parent == self.url:
            return
        count = 1
        while True:
            save = 'buildout_save_parent_location_%d' % count
            if save not in conf:
                conf[save] = old_parent
                break
            count += 1
        conf['parent_location'] = self.url
        self.write_conf(conf)

    def uncommitted_changes(self):
        """True if we have uncommitted changes."""
        return bool(check_output(['bzr', 'status', self.target_dir],
                                 env=SUBPROCESS_ENV))

    def parents(self):
        """Return current revision.

        Must be used in conjunction with uncommitted_changes to be sure
        that we are indeed on this revision
        """

        return [check_output(['bzr', 'revno', '--tree', self.target_dir],
                             env=SUBPROCESS_ENV).strip()]

    def clean(self):
        if not os.path.exists(self.target_dir):
            # not branched yet, there's nothing to clean
            return
        with working_directory_keeper:
            os.chdir(self.target_dir)
            subprocess.check_call(['bzr', 'clean-tree',
                                   '--ignored', '--force'])

    def _update(self, revision):
        """Update existing branch at target dir to given revision.

        raise UpdateError in case of problems."""

        update_check_call(['bzr', 'up', '-r', revision, self.target_dir],
                          env=SUBPROCESS_ENV)
        logger.info("Updated %r to revision %s", self.target_dir, revision)

    def get_revid(self, revision):
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

    def is_fixed_revision(self, revstr):
        """True iff the given revision string is for a fixed revision."""

        revstr = revstr.strip()  # one never knows
        if not revstr or revstr.startswith('last:'):
            return False
        try:
            revno = int(revstr)
        except ValueError:
            return True  # a string is either a tag or a revid: spec
        else:
            return revno >= 0

    def get_update(self, revision):
        """Ensure that target_dir is a branch of url at specified revision.

        If target_dir already exists, does a simple pull.
        Offline-mode: no branch nor pull, but update.
        In all cases, an attempt to update is performed before any pull
        """
        target_dir = self.target_dir
        offline = self.offline
        clear_locks = self.clear_locks

        if not os.path.exists(target_dir):
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

            self.update_conf()

            if self.is_fixed_revision(revision):
                try:
                    self._update(revision)
                    return
                except UpdateError:
                    if offline:
                        raise

            if offline:
                logger.info("Offline mode, no pull for revision %r", revision)
            else:
                self._pull()
            if not (offline and
                    self.options.get('bzr-init') == 'stacked-branch'):
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
        else:
            raise Exception("Unsupported option %r" % bzr_opt)

        if revision:
            branch_cmd.extend(['-r', revision])

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
