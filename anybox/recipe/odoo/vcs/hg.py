import os
import logging
import subprocess
import warnings
from ConfigParser import ConfigParser
from ConfigParser import NoOptionError
from ConfigParser import NoSectionError
from zc.buildout import UserError
from .base import BaseRepo
from .base import SUBPROCESS_ENV
from .base import update_check_call
from ..utils import check_output

logger = logging.getLogger(__name__)


class HgRepo(BaseRepo):

    vcs_control_dir = '.hg'

    vcs_official_name = 'Mercurial'

    def update_hgrc_paths(self):
        """Update hgrc paths section if needed.

        Old paths are kept in renamed form: buildout_save_%d."""
        parser = ConfigParser()
        hgrc_path = os.path.join(self.target_dir, '.hg', 'hgrc')
        parser.read(hgrc_path)  # does not fail if file does not exist

        previous = None
        try:
            previous = parser.get('paths', 'default')
        except NoOptionError:
            logger.info("No 'default' value for [paths] in %s, will set one",
                        hgrc_path)
        except NoSectionError:
            logger.info("Creating [paths] section in %s", hgrc_path)
            parser.add_section('paths')

        if previous == self.url:
            return

        if previous is not None:
            count = 1
            while True:
                save = 'buildout_save_%d' % count
                try:
                    parser.get('paths', save)
                except NoOptionError:
                    break
                count += 1
            parser.set('paths', save, previous)
            logger.info("Change of origin URL, saving previous value as %r in "
                        "[paths] section of %s", save, hgrc_path)

        parser.set('paths', 'default', self.url)
        f = open(hgrc_path, 'w')
        parser.write(f)
        f.close()

    def uncommitted_changes(self):
        """True if we have uncommitted changes."""
        return bool(check_output(['hg', '--cwd', self.target_dir, 'status'],
                                 env=SUBPROCESS_ENV))

    def parents(self, pip_compatible=False):
        """Return full hash of parent nodes.

        :param pip_compatible: ignored, all Hg revspecs are pip compatible
        """
        return check_output(['hg', '--cwd', self.target_dir, 'parents',
                             '--template={node}'],
                            env=SUBPROCESS_ENV).split()

    def have_fixed_revision(self, revstr):
        warnings.warn("have_fixed_revision() is deprecated and has been "
                      "renamed to is_local_fixed_revision()",
                      DeprecationWarning)
        return self.is_local_fixed_revision(revstr)

    def is_local_fixed_revision(self, revstr):
        """True if revstr is a fixed revision that we already have.

        Check is done for known tags (except tip) and known nodes identified
        by a long enough (12 char) prefix of their hexadecimal hash.

        Summary of collision cases for hg up:

        - a revision number has precedence over a tag identically named
        - a tag that is a strict prefix of a full hexadecimal node hash wins
          over that node.
        - a full hexadecimal node hash wins over a tag that would be
          identically named (someone would need to be really disturbed to do
          that in real life).
        - a hexadecimal node that coincides with a decimal revision number is
          not something I can test :-)

        In theory, a 12 char hexadecimal node hash could be shadowed by an
        incoming tag. But also, any tag could be overridden. These are
        considered to be fixed anyway for convenience in sensible use-cases.

        People having CI robots involving tags that do get overridden by a
        third party upstream should complain to upstream for utterly bad
        practices.
        """
        revstr = revstr.strip()
        if revstr == 'tip' or not revstr:
            return False

        try:
            out = check_output(['hg', '--cwd', self.target_dir, 'log',
                                '-r', revstr,
                                '--template={node}\n{tags}\n{rev}'],
                               env=SUBPROCESS_ENV)
        except subprocess.CalledProcessError:
            return False

        node, tags, rev = out.split(os.linesep)

        if node.startswith(revstr):
            # if too short, can be superseded by an incoming tag
            if len(revstr) >= 12:
                logger.info("[hg] Found requested revision %r in %s",
                            revstr, self.target_dir)
                return True

        if revstr == rev:
            logger.warn("[hg] In repo %s, you should not pinpoint revision "
                        "by a local revision number such as %r",
                        self.target_dir, revstr)
            # but indeed, nothing can change it (unless one day a node has
            # exactly that hash code, chances are...)
            return True

        if revstr in tags.split():
            logger.info("[hg] In repo %s, found tag %r as %s",
                        self.target_dir, revstr, node)
            return True

        return False

    def clean(self):
        if not os.path.isdir(self.target_dir):
            return

        try:
            subprocess.check_call(['hg', 'purge', '--cwd', self.target_dir])
        except subprocess.CalledProcessError as exc:
            if exc.returncode == 255:
                # fallback to default implementation
                logger.warn("The 'purge' Mercurial extension is not "
                            "activated. Do 'hg help purge' for more details "
                            "Falling back to default cleaning implementation")
                super(HgRepo, self).clean()

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
                raise UserError(
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
            if self.is_local_fixed_revision(revision):
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
