# coding: utf-8
from os.path import join
import sys, logging, shutil, re
from anybox.recipe.openerp.base import BaseRecipe

logger = logging.getLogger(__name__)

class WebClientRecipe(BaseRecipe):
    """Recipe for web client install and config
    """
    archive_filenames = {'6.0': 'openerp-web-%s.tar.gz'}
    requirements = ('setuptools',)

    def preinstall_version_check(self):
        split = self.version_wanted.split()
        if len(split) != 1:
            # not much to say before any attempt for custom or vcs versions
            return
        try:
            version = re.match(r'(\d+)[.](\d+)', split[0])
            version = int(version.group(1)), int(version.group(2))
        except (ValueError, TypeError, AttributeError):
            logger.info("Version not understood: %r. Skipped before install "
                        "checks", self.version_wanted)
            return
        if version >= (6, 1):
            logger.error("Aborting: don't use the openerp webclient recipe "
                         "for versions >= 6.1, as "
                         "there is no separate web client in these versions."
                         "Simply use the web part of the OpenERP server.")
            sys.exit(1)

    def _create_default_config(self):
        if self.version_detected[:3] == '6.0':
            shutil.copyfile(join(self.openerp_dir, 'doc', 'openerp-web.cfg'),
                            self.config_path)

    def _install_startup_scripts(self):
        script_name = self.options.get('script_name', 'start_' + self.name)
        self._install_script(script_name, self._create_startup_script())

    def _create_startup_script(self):
        """Return startup_script content
        """
        paths = [ self.openerp_dir ]
        paths.extend([egg.location for egg in self.ws])
        if self.version_detected[:3] == '6.0':
            ext = '.py'
            config = '-c %s' % self.config_path
        else:
            ext = ''
            config = ''
        script = ('#!/bin/sh\n'
                  'export PYTHONPATH=%s\n'
                  'cd "%s"\n'
                  'exec %s openerp-web%s %s $@') % (
                    ':'.join(paths),
                    self.openerp_dir,
                    self.buildout['buildout']['executable'],
                    ext,
                    config)
        return script

