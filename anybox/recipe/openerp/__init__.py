# coding: utf-8
from os.path import join, basename
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
        self.downloads = join(self.buildout_dir, 'downloads')
        self.version = None
        self.parts = self.buildout['buildout']['parts-directory']

        if 'version' in self.options:
            self.version = self.options['version']
            self.type = 'official'
            self.archive = self.archive_filename % self.version
            self.archive_path = join(self.downloads, self.archive)
            self.url = DOWNLOAD_URL + self.archive
        if 'url' in self.options:
            self.type = 'personal'
            self.url = self.options['url']
            # handle bzr branches
            if self.url.startswith('bzr+'):
                self.type = 'bzr'
                self.url = self.url[4:]
            self.archive = self.name + '_' + self.url.split('/')[-1]
        if 'url' not in self.options and 'version' not in self.options:
            raise Exception('You must specify either the version or url')
        
        self.openerp_dir = join(self.parts, self.archive)
        if self.type in ['official', 'personal']:
            self.openerp_dir = self.openerp_dir.replace('.tar.gz', '')

        self.etc = join(self.buildout_dir, 'etc')
        self.bin_dir = self.buildout['buildout']['bin-directory']
        self.config_path = join(self.etc, self.name + '.cfg')
        for d in self.downloads, self.etc:
            if not os.path.exists(d):
                logger.info('Created %s/ directory' % basename(d))
                os.mkdir(d)

    def install(self):
        installed = []
        os.chdir(self.parts)

        if self.type in ['official', 'personal']:
            # download and extract
            if not os.path.exists(self.archive_path):
                logger.info("Downloading %s ..." % self.url)
                urllib.urlretrieve(self.url, self.archive_path)
    
            if not os.path.exists(self.openerp_dir):
                logger.info(u'Extracting to %s ...' % self.openerp_dir)
                tar = tarfile.open(self.archive_path)
                tar.extractall()
                tar.close()
        elif self.type == 'bzr':
            revision = ''
            if self.version is not None:
                revision = "-r %s" % self.version
            if not os.path.exists(self.openerp_dir):
                cwd = os.getcwd()
                os.chdir(self.parts)
                logger.info("Branching %s ..." % self.url)
                subprocess.call('bzr branch --stacked %s %s %s' % (revision, self.url, self.archive), shell=True)
                os.chdir(cwd)
            else:
                cwd = os.getcwd()
                os.chdir(self.openerp_dir)
                logger.info("Updating branch ...")
                subprocess.call('bzr pull %s' % revision, shell=True)
                subprocess.call('bzr up %s' % revision, shell=True)
                os.chdir(cwd)


        # ugly method to extract requirements
        os.chdir(self.openerp_dir)
        old_setup = setuptools.setup
        def new_setup(*args, **kw):
            self.requirements.extend(kw['install_requires'])
        setuptools.setup = new_setup
        sys.path.insert(0, '.')
        with open(join(self.openerp_dir,'setup.py'), 'rb') as f:
            try:
                imp.load_module('setup', f, 'setup.py', ('.py', 'r', imp.PY_SOURCE))
            except SystemExit, e:
                if 'dsextras' in e.message:
                    logger.info('Please first install PyGObject and PyGTK !')
                else:
                    raise EnvironmentError('Problem while reading openerp setup.py: ' + e.message)
        _ = sys.path.pop(0)
        setuptools.setup = old_setup

        # install requirements and scripts
        if 'eggs' not in self.options:
            self.options['eggs'] = '\n'.join(self.requirements)
        else:
            self.options['eggs'] += '\n' + '\n'.join(self.requirements)
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
        if os.path.exists(self.config_path):
            os.remove(self.config_path)
        logger.info('Creating config file: ' + join(basename(self.etc), basename(self.config_path)))
        self._create_config()

        # modify the config file according to recipe options
        config = ConfigParser.SafeConfigParser()
        config.read(self.config_path)
        for recipe_option in self.options:
            if '.' not in recipe_option:
                continue
            section, option = recipe_option.split('.', 1)
            if not config.has_section(section):
                config.add_section(section)
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
    requirements = []

    def _create_config(self):
        """Create and modify the config file
        """
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
    requirements = ['setuptools']

    def _create_config(self):
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
    requirements = []

    def _create_config(self):
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

