import os
import logging
import subprocess
import urlparse
import urllib
from StringIO import StringIO

from ..utils import use_or_open
from ..utils import working_directory_keeper
from .base import SUBPROCESS_ENV
from .base import BaseRepo
from .base import update_check_call
from .base import UpdateError

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
        p = subprocess.Popen(['bzr', 'status', self.target_dir],
                             stdout=subprocess.PIPE, env=SUBPROCESS_ENV)
        return bool(p.communicate()[0])

    def parents(self):
        """Return current revision.

        Must be used in conjunction with uncommitted_changes to be sure
        that we are indeed on this revision
        """

        p = subprocess.Popen(['bzr', 'revno', '--tree', self.target_dir],
                             stdout=subprocess.PIPE, env=SUBPROCESS_ENV)
        return [p.communicate()[0].strip()]

    def clean(self):
        if not os.path.exists(self.target_dir):
            # not branched yet, there's nothing to clean
            return
        with working_directory_keeper:
            os.chdir(self.target_dir)
            subprocess.check_call(['bzr', 'clean-tree', '--ignored', '--force'])

    def _update(self, revision):
        """Update existing branch at target dir to given revision.

        raise UpdateError in case of problems."""

        update_check_call(['bzr', 'up', '-r', revision, self.target_dir],
                          env=SUBPROCESS_ENV)
        logger.info("Updated %r to revision %s", self.target_dir, revision)

    def get_revid(self, revision):
        with working_directory_keeper:
            os.chdir(self.target_dir)
            p = subprocess.Popen(['bzr', 'log', '--show-ids', '-r', revision],
                                 stdout=subprocess.PIPE, env=SUBPROCESS_ENV)
            log = p.communicate()[0].split(os.linesep)
            prefix = 'revision-id:'
            for line in log:
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
        url = self.url
        offline = self.offline
        clear_locks = self.clear_locks

        if not os.path.exists(target_dir):
            # TODO case of local url ?
            if offline:
                raise IOError(
                    "bzr branch %s does not exist; cannot branch it from "
                    "%s (offline mode)" % (target_dir, url))

            logger.info("Branching %s ...", url)
            branch_cmd = ['bzr', 'branch']
            if self.options.get('bzr-stacked-branches',
                                'false').strip().lower() == 'true':
                branch_cmd.append('--stacked')

            if revision:
                branch_cmd.extend(['-r', revision])
            branch_cmd.extend([url, target_dir])
            subprocess.check_call(branch_cmd, env=SUBPROCESS_ENV)
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
            self._update(revision)

    def _pull(self):
        logger.info("Pull for branch %s ...", self.target_dir)
        update_check_call(['bzr', 'pull', '-d', self.target_dir],
                          env=SUBPROCESS_ENV)

    def archive(self, target_path):
        with working_directory_keeper:
            os.chdir(self.target_dir)
            subprocess.check_call(['bzr', 'export', target_path])
