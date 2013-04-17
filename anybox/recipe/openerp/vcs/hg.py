import os
import logging
import subprocess
from ConfigParser import ConfigParser
from ConfigParser import NoOptionError
from .base import BaseRepo
from .base import SUBPROCESS_ENV
from .base import update_check_call

logger = logging.getLogger(__name__)


class HgRepo(BaseRepo):

    vcs_control_dir = '.hg'

    def update_hgrc_paths(self):
        """Update hgrc paths section if needed.

        Old paths are kept in renamed form: buildout_save_%d."""
        parser = ConfigParser()
        hgrc_path = os.path.join(self.target_dir, '.hg', 'hgrc')
        parser.read(hgrc_path)
        default = parser.get('paths', 'default')
        if default == self.url:
            return

        count = 1
        while True:
            save = 'buildout_save_%d' % count
            try:
                parser.get('paths', save)
            except NoOptionError:
                break
            count += 1

        parser.set('paths', save, default)
        parser.set('paths', 'default', self.url)
        f = open(hgrc_path, 'w')
        parser.write(f)
        f.close()

    def uncommitted_changes(self):
        """True if we have uncommitted changes."""
        p = subprocess.Popen(['hg', '--cwd', self.target_dir, 'status'],
                             stdout=subprocess.PIPE, env=SUBPROCESS_ENV)
        return bool(p.communicate()[0])

    def parents(self):
        """Return full hash of parent nodes. """
        p = subprocess.Popen(['hg', '--cwd', self.target_dir, 'parents',
                              '--template={node}'],
                             stdout=subprocess.PIPE, env=SUBPROCESS_ENV)
        return p.communicate()[0].split()

    def have_fixed_revision(self, revstr):
        """True if revstr is a fixed revision that we already have.

        Fixed in this case means that revstr is not an active branch
        """
        revstr = revstr.strip()
        if revstr == 'tip' or not revstr:
            return False
        try:
            subprocess.check_call(['hg', '--cwd', self.target_dir, 'log',
                                   '-r', revstr,
                                   '--template=[hg] found {rev}:{node}\n'],
                                  env=SUBPROCESS_ENV)
        except subprocess.CalledProcessError:
            return False

        # eliminate active branches
        p = subprocess.Popen(
            ['hg', '--cwd', self.target_dir, 'branches', '--active'],
            stdout=subprocess.PIPE, env=SUBPROCESS_ENV)
        branches = p.communicate()[0]
        for branch in branches.split(os.linesep):
            if branch and branch.split()[0] == revstr:
                return False

        return True

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
                raise IOError(
                    "hg repository %r does not exist; "
                    "cannot clone it from %r (offline mode)" % (target_dir,
                                                                url))

            logger.info("Cloning %s ...", url)
            clone_cmd = ['hg', 'clone']
            if revision:
                clone_cmd.extend(['-r', revision])
            clone_cmd.extend([url, target_dir])
            subprocess.check_call(clone_cmd, env=SUBPROCESS_ENV)
        else:
            self.update_hgrc_paths()
            # TODO what if remote repo is actually local fs ?
            if self.have_fixed_revision(revision):
                self._update(revision)
                return

            if not offline:
                self._pull()
            self._update(revision)

    def _pull(self):
        logger.info("Pull for hg repo %r ...", self.target_dir)
        subprocess.check_call(['hg', '--cwd', self.target_dir, 'pull'],
                              env=SUBPROCESS_ENV)

    def _update(self, revision):
        target_dir = self.target_dir
        logger.info("Updating %s to revision %s", target_dir, revision)
        up_cmd = ['hg', '--cwd', target_dir, 'up']
        if revision:
            up_cmd.extend(['-r', revision])
        update_check_call(up_cmd, env=SUBPROCESS_ENV)

    def archive(self, target_path):
        subprocess.check_call(['hg', '--cwd', self.target_dir,
                               'archive', target_path])
