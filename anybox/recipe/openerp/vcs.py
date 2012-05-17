import os
import subprocess
import logging
import shutil
from StringIO import StringIO

from utils import working_directory_keeper
logger = logging.getLogger(__name__)

SUBPROCESS_ENV = os.environ.copy()
SUBPROCESS_ENV['PYTHONPATH'] = SUBPROCESS_ENV.pop(
    'BUILDOUT_ORIGINAL_PYTHONPATH', '')

SUPPORTED = {}

class UpdateError(subprocess.CalledProcessError):
    """Specific class for errors occurring during updates of existing repos.
    """

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

def get_update(vcs_type, target_dir, url, revision, **options):
    """General entry point."""
    cls = SUPPORTED.get(vcs_type)
    if cls is None:
        raise ValueError("Unsupported VCS type: %r" % vcs_type)

    cls(target_dir, url, **options)(revision)

class HgRepo(BaseRepo):

    def get_update(self, revision):
        """Ensure that target_dir is a clone of url at specified revision.

        If target_dir already exists, does a simple pull.
        Offline-mode: no clone nor pull, but update.
        """
        target_dir = self.target_dir
        url = self.url
        offline = self.offline

        if not os.path.exists(target_dir):
            # TODO case of local url ?
            if offline:
                raise IOError("hg repository %r does not exist; cannot clone it from %r (offline mode)" % (target_dir, url))

            logger.info("Cloning %s ...", url)
            clone_cmd = ['hg', 'clone']
            if revision:
                clone_cmd.extend(['-r', revision])
            clone_cmd.extend([url, target_dir])
            subprocess.check_call(clone_cmd, env=SUBPROCESS_ENV)
        else:
            # TODO what if remote repo is actually local fs ?
            if not offline:
                logger.info("Pull for hg repo %r ...", target_dir)
                subprocess.check_call(['hg', '--cwd', target_dir, 'pull'],
                                      env=SUBPROCESS_ENV)
            if revision:
                logger.info("Updating %s to revision %s",
                            target_dir, revision)
                up_cmd = ['hg', '--cwd', target_dir, 'up']
                if revision:
                    up_cmd.extend(['-r', revision])
                subprocess.check_call(up_cmd, env=SUBPROCESS_ENV)

SUPPORTED['hg'] = HgRepo

class BzrBranch(BaseRepo):
    """Represent a Bazaar branch tied to a reference branch."""

    def get_update(self, revision):
        """Ensure that target_dir is a branch of url at specified revision.

        If target_dir already exists, does a simple pull.
        Offline-mode: no branch nor pull, but update.
        """
        target_dir = self.target_dir
        url = self.url
        offline = self.offline
        clear_locks = self.clear_locks

        if not os.path.exists(target_dir):
            # TODO case of local url ?
            if offline:
                raise IOError("bzr branch %s does not exist; cannot branch it from %s (offline mode)" % (target_dir, url))

            logger.info("Branching %s ...", url)
            branch_cmd = ['bzr', 'branch', '--stacked']
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
                # works for older ones as well (fortunately we don't need a pty)
                p = subprocess.Popen(['bzr', 'break-lock', target_dir],
                                     subprocess.PIPE)
                out, err = p.communicate(input='y')
                if p.returncode != 0:
                    raise subprocess.CalledProcessError(
                        p.returncode, repr(['bzr', 'break-lock', target_dir]))

            if not offline:
                logger.info("Pull for branch %s ...", target_dir)
                try:
                    subprocess.check_call(['bzr', 'pull',
                                           '-d', target_dir],
                                          env=SUBPROCESS_ENV)
                except subprocess.CalledProcessError, e:
                    raise UpdateError(e.returncode, e.cmd)

            if revision:
                logger.info("Update to revision %s", revision)
                subprocess.check_call(['bzr', 'up', '-r', revision, target_dir],
                                      env=SUBPROCESS_ENV)

SUPPORTED['bzr'] = BzrBranch

class GitRepo(BaseRepo):
    """Represent a Git clone tied to a reference branch."""

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
                    raise IOError("git repository %s does not exist; cannot clone it from %s (offline mode)" % (target_dir, url))

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
                                target_dir,revision)
                    subprocess.check_call(['git', 'checkout', rev_str])


SUPPORTED['git'] = GitRepo

class SvnCheckout(BaseRepo):

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
                    raise IOError("svn checkout %s does not exist; cannot checkout  from %s (offline mode)" % (target_dir, url))

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

SUPPORTED['svn'] = SvnCheckout
