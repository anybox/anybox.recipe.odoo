# coding: utf-8
from os.path import join
import sys, logging
from utils import working_directory_keeper
from anybox.recipe.openerp.base import BaseRecipe

logger = logging.getLogger(__name__)

class GtkClientRecipe(BaseRecipe):
    """Recipe for gtk client and config
    """
    archive_filenames = {'6.0': 'openerp-client-%s.tar.gz',
                        '6.1': 'openerp-client-%s.tar.gz' }
    recipe_requirements = () # neither PyGTK nor PyGObject can be locally built
    requirements = ('pydot', )

    def _create_default_config(self):
        bin_dir = join(self.openerp_dir, 'bin')
        with working_directory_keeper:
            # import translate from openerp instead of python
            sys.path.insert(0, bin_dir)
            import gtk.glade
            import release
            __version__ = release.version
            import __builtin__
            __builtin__.__dict__['openerp_version'] = __version__
            import translate
            translate.setlang()
            # temp replacing sys.argv to avoid buildout options
            # being interpreted by gtk client's OptionParser
            argv_bak = sys.argv
            sys.argv = [argv_bak[0]]
            import options
            options.configmanager(self.config_path).save()
            sys.argv = argv_bak

    def _install_startup_scripts(self):
        script_name = self.options.get('script_name', 'start_' + self.name)
        self._install_script(script_name, self._create_startup_script())

    def _create_startup_script(self):
        """Return startup_script content
        """
        paths = [ join(self.openerp_dir, 'bin') ]
        paths.extend([egg.location for egg in self.ws])
        script = ('#!/bin/sh\n'
                  'export PYTHONPATH=%s\n'
                  'cd "%s"\n'
                  'exec %s openerp-client.py -c %s $@') % (
                    ':'.join(paths),
                    join(self.openerp_dir, 'bin'),
                    self.buildout['buildout']['executable'],
                    self.config_path)
        return script

