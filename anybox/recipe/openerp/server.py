from os.path import join
from zc.buildout.easy_install import install
import os, sys, urllib, tarfile, setuptools, logging, stat, imp
import subprocess
import ConfigParser
import zc.recipe.egg

logger = logging.getLogger(__name__)

DOWNLOAD_URL = 'http://www.openerp.com/download/stable/source/'
SERVER_FILENAME = 'openerp-server-%s.tar.gz'

class Server(object):

    def __init__(self, buildout, name, options):
        self.buildout, self.name, self.options = buildout, name, options
        self.buildout_dir = self.buildout['buildout']['directory']
        self.version = self.options['version']
        self.parts = self.buildout['buildout']['parts-directory']
        self.archive = SERVER_FILENAME % self.version
        self.downloads = join(self.buildout_dir, 'downloads')
        self.archive_path = join(self.downloads, self.archive)
        self.url = DOWNLOAD_URL + self.archive
        self.openerp_dir = join(self.parts, self.archive.replace('.tar.gz', ''))
        self.openerp = join(self.openerp_dir, 'bin')
        self.etc = join(self.buildout_dir, 'etc')
        self.bin_dir = self.buildout['buildout']['bin-directory']
        self.openerp_config = join(self.etc, self.name + '.cfg')
        if 'url' in self.options:
            self.url = self.options['url']
            self.archive = self.url.split('/')[-1]
        for d in self.downloads, self.etc:
            if not os.path.exists(d):
                logger.info('Created %s/ directory' % os.path.basename(d))
                os.mkdir(d)

    def install(self):
        installed = []
        os.chdir(self.parts)

        # download and extract
        if not os.path.exists(self.archive_path):
            logger.info("Downloading OpenERP...")
            urllib.urlretrieve(self.url, self.archive_path)

        if not os.path.exists(self.openerp_dir):
            logger.info(u'Extracting OpenERP...')
            tar = tarfile.open(self.archive_path)
            tar.extractall()
            tar.close()
            installed.append(self.openerp_dir)


        # ugly method to retrieve requirements
        os.chdir(self.openerp_dir)
        old_setup = setuptools.setup
        requirements = []
        def new_setup(*args, **kw):
            requirements.extend(kw['install_requires'])
        setuptools.setup = new_setup
        sys.path.insert(0, '.')
        with open(join(self.openerp_dir,'setup.py'), 'rb') as f:
            imp.load_module('setup', f, 'setup.py', ('.py', 'r', imp.PY_SOURCE))
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
        script = ('#!/bin/sh\n'
                  'export PYTHONPATH=%s\n'
                  'cd "%s"\n'
                  'exec %s openerp-server.py -c %s $@') % (
                    ':'.join(paths),
                    self.openerp,
                    self.buildout['buildout']['executable'],
                    self.openerp_config)

        os.chdir(self.bin_dir)
        if 'script_name' in self.options:
            script_name = self.options['script_name']
        else:
            script_name = 'start_%s' % self.name
        script_path = join(self.bin_dir, script_name)
        script_file = open(script_path, 'w')
        script_file.write(script)
        script_file.close()
        os.chmod(script_path, stat.S_IRWXU)
        installed.append(script_path)

        # create config file
        if not os.path.exists(self.openerp_config):
            logger.info('Creating config file')
            subprocess.check_call([
                self.buildout['buildout']['executable'],
                join(self.openerp, 'openerp-server.py'),
                '--stop-after-init', '-s', '-c', self.openerp_config])

        # update config file
        config = ConfigParser.SafeConfigParser()
        config.read(self.openerp_config)
        for option in self.options:
            if option in config.options('options'):
                config.set('options', option, self.options[option])
        with open(self.openerp_config, 'wb') as configfile:
            config.write(configfile)

        return installed


    update = install


