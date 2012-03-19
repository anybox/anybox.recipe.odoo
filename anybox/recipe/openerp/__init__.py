# coding: utf-8
from os.path import join, basename
import os, sys, urllib, tarfile, setuptools, logging, stat, imp
import subprocess
import ConfigParser
import zc.recipe.egg

logger = logging.getLogger(__name__)

DOWNLOAD_URL = { '6.0': 'http://www.openerp.com/download/stable/source/',
                 '6.1': 'http://nightly.openerp.com/6.1/releases/'
                }

class WorkingDirectoryKeeper(object):
    """A context manager to get back the working directory as it was before."""

    active = False

    def __enter__(self):
        if self.active:
            raise RuntimeError("Already in a working directory keeper !")
        self.wd = os.getcwd()
        self.active = True

    def __exit__(self, *exc_args):
        os.chdir(self.wd)
        self.active = False

working_directory_keeper = WorkingDirectoryKeeper()


class Base(object):
    """Base class for other recipes
    """

    def __init__(self, buildout, name, options):
        self.buildout, self.name, self.options = buildout, name, options
        self.b_options = self.buildout['buildout']
        self.buildout_dir = self.b_options['directory']
        # GR: would prefer lower() but doing as in 'zc.recipe.egg'
        self.offline = self.b_options['offline'] == 'true'

        self.downloads_dir = join(self.buildout_dir, 'downloads')
        self.version_wanted = None  # from the buildout
        self.version_detected = None  # from the openerp setup.py
        self.parts = self.buildout['buildout']['parts-directory']
        self.addons = self.options.get('addons')
        self.openerp_dir = None

        # set other variables depending on provided version or url
        if 'version' in self.options:
            self.version_wanted = self.options['version']

            # correct an assumed 6.1 version
            if self.version_wanted == '6.1':
                logger.warn('Version 6.1 does not exist. Assuming 6.1-1')
                self.version_wanted = '6.1-1'

            # Unsupported versions
            if self.version_wanted[:3] not in DOWNLOAD_URL.keys():
                raise Exception('OpenERP version %s is not supported' % self.version_wanted)

            self.type = 'official'
            if 'url' not in self.options:
                self.archive = self.archive_filename[self.version_wanted[:3]] % self.version_wanted
                self.archive_path = join(self.downloads_dir, self.archive)
                self.url = DOWNLOAD_URL[self.version_wanted[:3]] + self.archive

        if 'url' in self.options:
            self.type = 'personal'
            self.url = self.options['url']
            # handle bzr branches
            if self.url.startswith('bzr+'):
                self.type = 'bzr'
                self.url = self.url[4:]
            self.archive = self.name + '_' + self.url.strip('/').split('/')[-1]
        if 'url' not in self.options and 'version' not in self.options:
            raise Exception('You must specify either the version or url')

        self.openerp_dir = join(self.parts, self.archive)
        if self.type in ['official', 'personal']:
            self.openerp_dir = self.openerp_dir.replace('.tar.gz', '')

        self.etc = join(self.buildout_dir, 'etc')
        self.bin_dir = self.buildout['buildout']['bin-directory']
        self.config_path = join(self.etc, self.name + '.cfg')
        for d in self.downloads_dir, self.etc:
            if not os.path.exists(d):
                logger.info('Created %s/ directory' % basename(d))
                os.mkdir(d)

    def bzr_get_update(self, target_dir, url, revision):
        """Ensure that target_dir is a branch of url at specified revision.

        If target_dir already exists, does a simple pull.
        Offline-mode: no branch nor pull, but update.
        """
        rev_str = revision and '-r ' + revision or ''

        with working_directory_keeper:
            if not os.path.exists(target_dir):
                # TODO case of local url ?
                if self.offline:
                    raise IOError("bzr branch %s does not exist; cannot branch it from %s (offline mode)" % (target_dir, url))

                os.chdir(os.path.split(target_dir)[0])
                logger.info("Branching %s ...", url)
                subprocess.call('bzr branch --stacked %s %s %s' % (
                        rev_str, url, target_dir), shell=True)
            else:
                os.chdir(target_dir)
                # TODO what if bzr source is actually local fs ?
                if not self.offline:
                    logger.info("Pull for branch %s ...", target_dir)
                    subprocess.call('bzr pull', shell=True)
                if revision:
                    logger.info("Update to revision %s", revision)
                    subprocess.call('bzr up %s' % rev_str, shell=True)


    def hg_get_update(self, target_dir, url, revision):
        """Ensure that target_dir is a branch of url at specified revision.

        If target_dir already exists, does a simple pull.
        Offline-mode: no branch nor pull, but update.
        """
        rev_str = revision and '-r ' + revision or ''

        with working_directory_keeper:
            if not os.path.exists(target_dir):
                # TODO case of local url ?
                if self.offline:
                    raise IOError("hg repository %s does not exist; cannot clone it from %s (offline mode)" % (target_dir, url))

                os.chdir(os.path.split(target_dir)[0])
                logger.info("CLoning %s ...", url)
                subprocess.call('hg clone %s %s %s' % (
                        rev_str, url, target_dir), shell=True)
            else:
                os.chdir(target_dir)
                # TODO what if remote repo is actually local fs ?
                if not self.offline:
                    logger.info("Pull for hg repo %s ...", target_dir)
                    subprocess.call('hg pull', shell=True)
                if revision:
                    logger.info("Updating %s to revision %s",
                                target_dir, revision)
                    subprocess.call('hg up %s' % rev_str, shell=True)

    def git_get_update(self, target_dir, url, revision):
        """Ensure that target_dir is a branch of url at specified revision.

        If target_dir already exists, does a simple pull.
        Offline-mode: no branch nor pull, but update.
        """
        rev_str = revision

        with working_directory_keeper:
            if not os.path.exists(target_dir):
                # TODO case of local url ?
                if self.offline:
                    raise IOError("git repository %s does not exist; cannot clone it from %s (offline mode)" % (target_dir, url))

                os.chdir(os.path.split(target_dir)[0])
                logger.info("CLoning %s ...", url)
                subprocess.call('git clone -b %s %s %s' % (
                        rev_str, url, target_dir), shell=True)
            else:
                os.chdir(target_dir)
                # TODO what if remote repo is actually local fs ?
                if not self.offline:
                    logger.info("Pull for git repo %s (rev %s)...",
                                target_dir, rev_str)
                    subprocess.call('git pull %s %s' % (url, rev_str),
                                    shell=True)
                elif revision:
                    logger.info("Checkout %s to revision %s",
                                target_dir,revision)
                    subprocess.call('git checkout %s' % rev_str, shell=True)

    def svn_get_update(self, target_dir, url, revision):
        """Ensure that target_dir is a branch of url at specified revision.

        If target_dir already exists, does a simple pull.
        Offline-mode: no branch nor pull, but update.
        """
        rev_str = revision and '-r ' + revision or ''

        with working_directory_keeper:
            if not os.path.exists(target_dir):
                # TODO case of local url ?
                if self.offline:
                    raise IOError("svn checkout %s does not exist; cannot checkout  from %s (offline mode)" % (target_dir, url))

                os.chdir(os.path.split(target_dir)[0])
                logger.info("Checkouting %s ...", url)
                subprocess.call('svn checkout %s %s %s' % (
                        rev_str, url, target_dir), shell=True)
            else:
                os.chdir(target_dir)
                # TODO what if remote repo is actually local fs ?
                if self.offline:
                    logger.warning(
                        "Offline mode: keeping checkout %s in its current rev",
                        target_dir)
                else:
                    logger.info("Updating %s to revision %s...",
                                target_dir, revision)
                    subprocess.call('svn up %s %s' % (url, rev_str),
                                    shell=True)

    def install(self):
        installed = []
        os.chdir(self.parts)

        # install server
        if self.type in ['official', 'personal']:
            # download and extract
            if not os.path.exists(self.archive_path):
                if self.offline:
                    raise IOError("%s not found, and offline mode requested" % self.archive_path)
                logger.info("Downloading %s ..." % self.url)
                msg = urllib.urlretrieve(self.url, self.archive_path)
                if msg[1].type == 'text/html':
                    os.unlink(self.archive_path)
                    raise IOError('Wanted version was not found: %s' % self.url)

            if not os.path.exists(self.openerp_dir):
                logger.info(u'Extracting to %s ...' % self.openerp_dir)
                try:
                    tar = tarfile.open(self.archive_path)
                except:
                    raise IOError('The downloaded archive does not seem valid: %s' % self.archive_path)
                tar.extractall()
                tar.close()
        elif self.type == 'bzr':
            self.bzr_get_update(self.openerp_dir, self.url, self.version_wanted)

        # install addons
        # syntax: repo_type repo_url repo_dir revisionspec
        #         or an absolute or relative path
        if self.addons:
            addons_paths = []
            vcs_methods = dict(
                bzr=self.bzr_get_update,
                svn=self.svn_get_update,
                hg=self.hg_get_update,
                git=self.git_get_update)

            for line in self.addons.split('\n'):
                repo_type = line.split()[0] # may also be a path
                vcs_method = vcs_methods.get(repo_type)

                if vcs_method is not None:
                    repo_url, repo_dir, revisionspec = line.split()[1:]
                    vcs_method(join(self.buildout_dir, repo_dir),
                               repo_url, revisionspec)
                elif os.path.isabs(repo_type):
                    repo_dir = repo_type
                else:
                    repo_dir = join(self.buildout_dir, repo_type)

                assert os.path.isdir(repo_dir), (
                    "Not a directory: %r (aborting)" % repo_dir)

                addons_paths.append(repo_dir)
            addons_paths = ','.join(addons_paths)
            if 'options.addons_path' not in self.options:
                self.options['options.addons_path'] = ''
            self.options['options.addons_path'] += join(self.openerp_dir, 'bin', 'addons') + ','
            self.options['options.addons_path'] += addons_paths

        # ugly method to extract requirements from ugly setup.py of 6.0,
        # but works with 6.1 as well
        os.chdir(self.openerp_dir)
        old_setup = setuptools.setup
        def new_setup(*args, **kw):
            self.requirements.extend(kw['install_requires'])
            self.version_detected = kw['version']
        setuptools.setup = new_setup
        sys.path.insert(0, '.')
        with open(join(self.openerp_dir,'setup.py'), 'rb') as f:
            try:
                imp.load_module('setup', f, 'setup.py', ('.py', 'r', imp.PY_SOURCE))
            except SystemExit, exception:
                if 'dsextras' in exception.message:
                    raise EnvironmentError('Please first install PyGObject and PyGTK !')
                else:
                    raise EnvironmentError('Problem while reading OpenERP setup.py: ' + exception.message)
            except ImportError, exception:
                if 'babel' in exception.message:
                    raise EnvironmentError('OpenERP setup.py has an unwanted import Babel.\n'
                                           '=> First install Babel on your system or virtualenv :(\n'
                                           '(sudo aptitude install python-babel, or pip install babel)')
                else:
                    raise exception
            except Exception, exception:
                raise EnvironmentError('Problem while reading OpenERP setup.py: ' + exception.message)
        _ = sys.path.pop(0)
        setuptools.setup = old_setup

        # add openerp paths into the extra-paths
        if 'extra-paths' not in self.options:
            self.options['extra-paths'] = ''
        self.options['extra-paths'] = (
                '\n'.join([join(self.openerp_dir, 'bin'),
                           join(self.openerp_dir, 'bin', 'addons')]
                         )
                + '\n' + self.options['extra-paths'])

        # install requirements and scripts
        if 'eggs' not in self.options:
            self.options['eggs'] = '\n'.join(self.requirements)
        else:
            self.options['eggs'] += '\n' + '\n'.join(self.requirements)
        eggs = zc.recipe.egg.Scripts(self.buildout, '', self.options)
        ws = eggs.install()
        _, ws = eggs.working_set()
        self.ws = ws
        if self.version_detected is None:
            raise EnvironmentError('Version of OpenERP could not be detected')
        script = self._create_startup_script()

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
        self._create_default_config()

        # modify the config file according to recipe options
        config = ConfigParser.RawConfigParser()
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

    def _create_startup_script(self):
        raise NotImplementedError

    def _create_default_config(self):
        raise NotImplementedError

    update = install


class Server(Base):
    """Recipe for server install and config
    """
    archive_filename = { '6.0': 'openerp-server-%s.tar.gz',
                         '6.1': 'openerp-%s.tar.gz'}
    requirements = []
    ws = None

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
        paths = [ join(self.openerp_dir, 'openerp') ]
        paths.extend([egg.location for egg in self.ws])
        if self.version_detected[:3] == '6.0':
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


class WebClient(Base):
    """Recipe for web client install and config
    """
    archive_filename = {'6.0': 'openerp-web-%s.tar.gz'}
    requirements = ['setuptools']

    def _create_default_config(self):
        pass

    def _create_startup_script(self):
        """Return startup_script content
        """
        paths = [ self.openerp_dir ]
        paths.extend([egg.location for egg in self.ws])
        if self.version_detected[:3] == '6.0':
            ext = '.py'
        else:
            ext = ''
        script = ('#!/bin/sh\n'
                  'export PYTHONPATH=%s\n'
                  'cd "%s"\n'
                  'exec %s openerp-web%s $@') % (
                    ':'.join(paths),
                    self.openerp_dir,
                    self.buildout['buildout']['executable'],
                    ext)
        return script


class GtkClient(Base):
    """Recipe for gtk client and config
    """
    archive_filename = {'6.0': 'openerp-client-%s.tar.gz',
                        '6.1': 'openerp-client-%s.tar.gz' }
    requirements = []

    def _create_default_config(self):
        subprocess.check_call([self.script_path])

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

