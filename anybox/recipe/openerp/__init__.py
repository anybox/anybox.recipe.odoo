# coding: utf-8
from os.path import join, basename
from zc.buildout.easy_install import install
import os, sys, urllib, tarfile, setuptools, logging, stat, imp, shutil
import subprocess
import ConfigParser
import zc.recipe.egg

logger = logging.getLogger(__name__)

DOWNLOAD_URL = 'http://www.openerp.com/download/stable/source/'

class Base(object):
    """Base class for other recipes
    """

    def __init__(self, buildout, name, options):
        self.buildout, self.name, self.options = buildout, name, options
        self.buildout_dir = self.buildout['buildout']['directory']
        self.version = self.options['version']
        self.parts = self.buildout['buildout']['parts-directory']
        self.archive = self.archive_filename % self.version
        self.downloads = join(self.buildout_dir, 'downloads')
        self.archive_path = join(self.downloads, self.archive)
        self.url = DOWNLOAD_URL + self.archive
        self.openerp_dir = join(self.parts, self.archive.replace('.tar.gz', ''))
        self.etc = join(self.buildout_dir, 'etc')
        self.bin_dir = self.buildout['buildout']['bin-directory']
        self.config_path = join(self.etc, self.name + '.cfg')
        if 'url' in self.options:
            self.url = self.options['url']
            self.archive = self.url.split('/')[-1]
        for d in self.downloads, self.etc:
            if not os.path.exists(d):
                logger.info('Created %s/ directory' % basename(d))
                os.mkdir(d)

    def install(self):
        installed = []
        os.chdir(self.parts)

        # download and extract
        if not os.path.exists(self.archive_path):
            logger.info("Downloading...")
            urllib.urlretrieve(self.url, self.archive_path)

        if not os.path.exists(self.openerp_dir):
            logger.info(u'Extracting...')
            tar = tarfile.open(self.archive_path)
            tar.extractall()
            tar.close()

        # ugly method to extract requirements
        os.chdir(self.openerp_dir)
        old_setup = setuptools.setup
        requirements = []
        def new_setup(*args, **kw):
            requirements.extend(kw['install_requires'])
        setuptools.setup = new_setup
        sys.path.insert(0, '.')
        with open(join(self.openerp_dir,'setup.py'), 'rb') as f:
            try:
                imp.load_module('setup', f, 'setup.py', ('.py', 'r', imp.PY_SOURCE))
            except SystemExit, e:
                raise EnvironmentError('Problem while reading openerp setup.py: ' + e.message)
        _ = sys.path.pop(0)
        setuptools.setup = old_setup

        # install requirements and scripts
        if 'eggs' not in self.options:
            self.options['eggs'] = '\n'.join(requirements)
        else:
            self.options['eggs'] += '\n' + '\n'.join(requirements)
        eggs = zc.recipe.egg.Scripts(self.buildout, '', self.options)
        ws = eggs.install()
        _, ws = eggs.working_set()

        script = self._create_startup_script(ws)

        os.chdir(self.bin_dir)
        if 'script_name' in self.options:
            script_name = self.options['script_name']
        else:
            script_name = 'start_%s' % self.name
        self.script_path = join(self.bin_dir, script_name)
        script_file = open(self.script_path, 'w')
        script_file.write(script)
        script_file.close()
        os.chmod(self.script_path, stat.S_IRWXU)
        installed.append(self.script_path)

        # create the config file
        self._create_config()

        # modify config file according to recipe options
        config = ConfigParser.SafeConfigParser()
        config.read(self.config_path)
        for recipe_option in self.options:
            if '.' not in recipe_option:
                continue
            section, option = recipe_option.split('.', 1)
            config.set(section, option, self.options[recipe_option])
        with open(self.config_path, 'wb') as configfile:
            config.write(configfile)

        return installed

    def _create_startup_script(self, ws):
        raise NotImplementedError

    def _create_config(self):
        raise NotImplementedError

    update = install


class Server(Base):
    """Recipe for server install and config
    """
    archive_filename = 'openerp-server-%s.tar.gz'

    def _create_config(self):
        """Create and modify the config file
        """
        # create config file
        if not os.path.exists(self.config_path):
            logger.info('Creating config file: ' + basename(self.config_path))
            subprocess.check_call([
                self.script_path, '--stop-after-init', '-s'])

    def _create_startup_script(self, ws):
        """Return startup_script content
        """
        paths = [ join(self.openerp_dir, 'bin') ]
        paths.extend([egg.location for egg in ws])
        script = ('#!/bin/sh\n'
                  'export PYTHONPATH=%s\n'
                  'cd "%s"\n'
                  'exec %s openerp-server.py -c %s $@') % (
                    ':'.join(paths),
                    join(self.openerp_dir, 'bin'),
                    self.buildout['buildout']['executable'],
                    self.config_path)
        return script


class WebClient(Base):
    """Recipe for web client install and config
    """
    archive_filename = 'openerp-web-%s.tar.gz'

    def _create_config(self):
        # create config file
        logger.info('Creating config file: ' + basename(self.config_path))
        shutil.copyfile(join(self.openerp_dir, 'doc', 'openerp-web.cfg'),
                        self.config_path)

    def _create_startup_script(self, ws):
        """Return startup_script content
        """
        paths = [ self.openerp_dir ]
        paths.extend([egg.location for egg in ws])
        script = ('#!/bin/sh\n'
                  'export PYTHONPATH=%s\n'
                  'cd "%s"\n'
                  'exec %s openerp-web.py -c %s $@') % (
                    ':'.join(paths),
                    self.openerp_dir,
                    self.buildout['buildout']['executable'],
                    self.config_path)
        return script


class GtkClient(Base):
    """Recipe for gtk client and config
    """
    archive_filename = 'openerp-client-%s.tar.gz'

    def _create_config(self):
        # create config file
        if not os.path.exists(self.config_path):
            logger.info('Creating config file: ' + basename(self.config_path))
            subprocess.check_call([self.script_path])

    def _create_startup_script(self, ws):
        """Return startup_script content
        """
        paths = [ join(self.openerp_dir, 'bin') ]
        paths.extend([egg.location for egg in ws])
        script = ('#!/bin/sh\n'
                  'export PYTHONPATH=%s\n'
                  'cd "%s"\n'
                  'exec %s openerp-client.py -c %s $@') % (
                    ':'.join(paths),
                    join(self.openerp_dir, 'bin'),
                    self.buildout['buildout']['executable'],
                    self.config_path)
        return script

