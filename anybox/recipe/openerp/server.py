import os, sys, urllib, tarfile, setuptools, logging, stat
from zc.buildout.easy_install import install
import zc.recipe.egg
from os.path import join

logger = logging.getLogger(__name__)

DOWNLOAD_URL = 'http://www.openerp.com/download/stable/source/'
SERVER_FILENAME = 'openerp-server-%s.tar.gz'

class Server(object):

    def __init__(self, buildout, name, options):
        self.buildout, self.name, self.options = buildout, name, options
        self.version = self.options['version']
        self.parts = self.buildout['buildout']['parts-directory']
        self.archive = SERVER_FILENAME % self.version
        self.archive_path = join(self.parts, self.archive)
        self.url = DOWNLOAD_URL + self.archive
        self.openerp_dir = self.archive_path.replace('.tar.gz', '')
        self.openerp = join(self.openerp_dir, 'bin')
        if 'url' in self.options:
            self.url = self.options['url']
            self.archive = self.url.split('/')[-1]

    def install(self):
        installed = []
        os.chdir(self.parts)

        # download and extract
        if not os.path.exists(self.archive):
            logger.info("Downloading OpenERP...")
            urllib.urlretrieve(self.url, self.archive_path)
            logger.info(u'Extracting OpenERP...')
            tar = tarfile.open(self.archive)
            tar.extractall()
            tar.close()
            installed.extend([self.archive_path, self.openerp_dir])


        # ugly method to retrieve requirements
        os.chdir(self.openerp_dir)
        old_setup = setuptools.setup
        requirements = []
        def new_setup(*args, **kw):
            requirements.extend(kw['install_requires'])
        setuptools.setup = new_setup
        sys.path.insert(0, '.')
        import setup
        _ = sys.path.pop(0)
        setuptools.setup = old_setup

        # install requirements and scripts
        if 'eggs' not in self.options:
            self.options['eggs'] = '\n'.join(requirements)
        else:
            self.options['eggs'] += '\n' + '\n'.join(requirements)
        eggs = zc.recipe.egg.Scripts(self.buildout, '', self.options)
        eggs.install()
        _, ws = eggs.working_set()

        # create startup script
        paths = [ self.openerp ]
        paths.extend([egg.location for egg in ws])
        script = ('#!%s\n'
                  'import sys, imp\n'
                  'sys.path[0:0] = %s\n'
                  'imp.load_source("_", "%s")') % (
                    self.buildout['buildout']['executable'],
                    paths,
                    join(self.openerp, 'openerp-server.py'))

        bin_dir = self.buildout['buildout']['bin-directory']
        os.chdir(bin_dir)
        if 'script_name' in self.options:
            script_name = self.options['script_name']
        else:
            script_name = 'start_%s' % self.name
        script_path = join(bin_dir, script_name)
        script_file = open(script_path, 'w')
        script_file.write(script)
        script_file.close()
        os.chmod(script_path, stat.S_IRWXU)
        installed.append(script_path)

        return installed


    update = install


