# coding: utf-8
from os.path import join
import sys, logging
import subprocess
import zc.buildout
from anybox.recipe.openerp.base import BaseRecipe

logger = logging.getLogger(__name__)

class ServerRecipe(BaseRecipe):
    """Recipe for server install and config
    """
    archive_filenames = { '6.0': 'openerp-server-%s.tar.gz',
                         '6.1': 'openerp-%s.tar.gz'}
    recipe_requirements = ('babel',)
    requirements = ('pychart',)
    ws = None

    def merge_requirements(self):
        """Prepare for installation by zc.recipe.egg

         - add Pillow iff PIL not present in eggs option.
         - (OpenERP >= 6.1) develop the openerp distribution and require it

        For PIL, extracted requirements are not taken into account. This way,
        if at some point, 
        OpenERP introduce a hard dependency on PIL, we'll still install Pillow.
        The only case where PIL will have precedence over Pillow will thus be
        the case of a legacy buildout.
        See https://bugs.launchpad.net/anybox.recipe.openerp/+bug/1017252

        Once 'openerp' is required, zc.recipe.egg will take it into account
        and put it in needed scripts, interpreters etc.
        """
        if not 'PIL' in self.options.get('eggs', '').split():
            self.requirements.append('Pillow')
        if self.version_detected[:3] == '6.1':
            develop_dir = self.b_options['develop-eggs-directory']
            zc.buildout.easy_install.develop(self.openerp_dir, develop_dir)
            self.requirements.append('openerp')

        BaseRecipe.merge_requirements(self)

    def _create_default_config(self):
        """Create a default config file
        """
        if self.version_detected.startswith('6.0'):
            subprocess.check_call([self.script_path, '--stop-after-init', '-s'])
        else:
            sys.path.extend([self.openerp_dir])
            sys.path.extend([egg.location for egg in self.ws])
            from openerp.tools.config import configmanager
            configmanager(self.config_path).save()

    def _create_startup_script(self):
        """Return startup_script content
        """
        paths = [egg.location for egg in self.ws]
        if self.version_detected[:3] == '6.0':
            paths.append(self.openerp_dir, 'openerp')
            ext = '.py'
            bindir = join(self.openerp_dir, 'bin')
        else:
            ext = ''
            bindir = self.openerp_dir

        script = ('#!/bin/sh\n'
                  'export PYTHONPATH=%s\n'
                  'cd "%s"\n'
                  'exec %s openerp-server%s -c %s $@') % (
                    ':'.join(paths),
                    bindir,
                    self.buildout['buildout']['executable'],
                    ext,
                    self.config_path)
        return script


