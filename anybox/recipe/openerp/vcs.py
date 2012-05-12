import os
import subprocess
import logging
from utils import working_directory_keeper

logger = logging.getLogger(__name__)

SUBPROCESS_ENV = os.environ.copy()
SUBPROCESS_ENV['PYTHONPATH'] = SUBPROCESS_ENV.pop(
    'BUILDOUT_ORIGINAL_PYTHONPATH', '')

SUPPORTED = frozenset(('bzr', 'hg', 'git', 'svn'))

def hg_get_update(target_dir, url, revision, offline=False, **kw):
    """Ensure that target_dir is a clone of url at specified revision.

    If target_dir already exists, does a simple pull.
    Offline-mode: no clone nor pull, but update.
    """
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

def bzr_get_update(target_dir, url, revision, offline=False, clear_locks=False,
                   **kw):
    """Ensure that target_dir is a branch of url at specified revision.

    If target_dir already exists, does a simple pull.
    Offline-mode: no branch nor pull, but update.
    """
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
            logger.info("Break-lock for branch %s ...", target_dir)
            subprocess.check_call(['bzr', 'break-lock', target_dir])
        if not offline:
            logger.info("Pull for branch %s ...", target_dir)
            subprocess.check_call(['bzr', 'pull', '-d', target_dir],
                                  env=SUBPROCESS_ENV)
        if revision:
            logger.info("Update to revision %s", revision)
            subprocess.check_call(['bzr', 'up', '-r', revision, target_dir],
                                  env=SUBPROCESS_ENV)


def git_get_update(target_dir, url, revision, offline=False, **kw):
    """Ensure that target_dir is a branch of url at specified revision.

    If target_dir already exists, does a simple pull.
    Offline-mode: no branch nor pull, but update.
    """
    rev_str = revision

    with working_directory_keeper:
        if not os.path.exists(target_dir):
            # TODO case of local url ?
            if offline:
                raise IOError("git repository %s does not exist; cannot clone it from %s (offline mode)" % (target_dir, url))

            os.chdir(os.path.split(target_dir)[0])
            logger.info("Cloning %s ...", url)
            subprocess.check_call('git clone -b %s %s %s' % (
                rev_str, url, target_dir), shell=True)
        else:
            os.chdir(target_dir)
            # TODO what if remote repo is actually local fs ?
            if not offline:
                logger.info("Pull for git repo %s (rev %s)...",
                            target_dir, rev_str)
                subprocess.check_call('git pull %s %s' % (url, rev_str),
                                      shell=True)
            elif revision:
                logger.info("Checkout %s to revision %s",
                            target_dir,revision)
                subprocess.check_call('git checkout %s' % rev_str, shell=True)

def svn_get_update(self, target_dir, url, revision, offline=False, **kw):
    """Ensure that target_dir is a branch of url at specified revision.

    If target_dir already exists, does a simple pull.
    Offline-mode: no branch nor pull, but update.
    """
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


