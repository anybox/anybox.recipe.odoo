
# coding: utf-8
from os.path import join, basename
import os, sys, urllib, tarfile, setuptools, logging, stat, imp, shutil
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


class BaseRecipe(object):
    """Base class for other recipes
    """

    def __init__(self, buildout, name, options):
        self.buildout, self.name, self.options = buildout, name, options
        self.b_options = self.buildout['buildout']
        self.buildout_dir = self.b_options['directory']
        # GR: would prefer lower() but doing as in 'zc.recipe.egg'
        self.offline = self.b_options['offline'] == 'true'

        self.downloads_dir = self.make_absolute(
            self.b_options.get('openerp-downloads-directory', 'downloads'))
        self.version_wanted = None  # from the buildout
        self.version_detected = None  # from the openerp setup.py
        self.parts = self.buildout['buildout']['parts-directory']
        self.addons = self.options.get('addons')
        self.openerp_dir = None
        self.url = None
        self.archive_filename = None
        self.archive_path = None # downloaded tar.gz

        self.etc = self.make_absolute('etc')
        self.bin_dir = self.buildout['buildout']['bin-directory']
        self.config_path = join(self.etc, self.name + '.cfg')
        for d in self.downloads_dir, self.etc:
            if not os.path.exists(d):
                logger.info('Created %s/ directory' % basename(d))
                os.mkdir(d)

        if 'version' not in self.options:
            raise Exception('You must specify the version')
                
        # set variables depending on provided version or url
        self.version_wanted = self.options['version']

        # correct an assumed 6.1 version
        if self.version_wanted == '6.1':
            logger.warn('Version 6.1 does not exist. Assuming 6.1-1')
            self.version_wanted = '6.1-1'

        # downloadable version, or local path
        version_split = self.version_wanted.split()
        if len(version_split) == 1:
            if not os.path.exists(self.version_wanted):
                # Unsupported versions
                if self.version_wanted[:3] not in DOWNLOAD_URL.keys():
                    raise Exception('OpenERP version %s is not supported' % self.version_wanted)
                self.type = 'downloadable'
                self.archive_filename = self.archive_filenames[self.version_wanted[:3]] % self.version_wanted
                self.archive_path = join(self.downloads_dir, self.archive_filename)
                self.url = DOWNLOAD_URL[self.version_wanted[:3]] + self.archive_filename
            else:
                self.type = 'local'
                self.openerp_dir = self.version_wanted

        # remote repository
        if getattr(self, 'type', None) is None:
            if len(version_split) != 4:
                raise ValueError("Unrecognized version specification: %r "
                                 "(expecting type, url, target, revision for "
                                 "remote repository or explicit download) " % (
                        version_split))

            self.type, self.url, repo_dir, self.version_wanted = version_split
            self.openerp_dir = join(self.parts, repo_dir)


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
                    logger.info("Updating %s to location %s, revision %s...",
                                target_dir, url, revision)
                    # switch is necessary in order to move in tags
                    # TODO support also change of svn root url
                    subprocess.call('svn switch %s' % url, shell=True)
                    subprocess.call('svn up %s' % rev_str,
                                    shell=True)

    def make_absolute(self, path):
        """Make a path absolute if needed.

        If not already absolute, it is interpreted as relative to the
        buildout directory."""
        if os.path.isabs(path):
            return path
        return join(self.buildout_dir, path)

    def sandboxed_tar_extract(self, sandbox, tarfile, first=None):
        """Extract those members that are below the tarfile path 'sandbox'.

        The tarfile module official doc warns against attacks with .. in tar.

        The option to start with a first member is useful for this case, since
        the recipe consumes a first member in the tar file to get the openerp
        main directory in parts.
        It is taken for granted that this first member has already been checked.
        """

        if first is not None:
            tarfile.extract(first)

        for tinfo in tarfile:
            if tinfo.name.startswith(sandbox + '/'):
                tarfile.extract(tinfo)
            else:
                logger.warn('Tarball member %r is outside of %r. Ignored.',
                            tinfo, sandbox)

    def retrieve_addons(self):
        """Parse the addons option line, download and return a list of paths.

        syntax: repo_type repo_url repo_dir repo_rev [options]
              or an absolute or relative path
        options are themselves in the key=value form
        """
        if not self.addons:
            return []

        addons_paths = []

        for line in self.addons.split('\n'):
            split = line.split()
            repo_type = split[0]
            spec_len = repo_type == 'local' and 2 or 4

            addons_options = dict(opt.split('=') for opt in split[spec_len:])

            if repo_type == 'local':
                repo_dir = self.make_absolute(split[1])
            else:
               vcs_method = getattr(self, '%s_get_update' % repo_type, None)
               if vcs_method is None:
                   raise RuntimeError("Don't know how to handle "
                                      "vcs type %s" % repo_type)

               repo_url, repo_dir, repo_rev = split[1:4]

               repo_dir = self.make_absolute(repo_dir)
               vcs_method(repo_dir, repo_url, repo_rev)

            subdir = addons_options.get('subdir')
            addons_dir = subdir and join(repo_dir, subdir) or repo_dir
            assert os.path.isdir(addons_dir), (
                "Not a directory: %r (aborting)" % addons_dir)

            manifest = os.path.join(addons_dir, '__openerp__.py')
            if os.path.isfile(manifest):
                # repo is a single addon, put it actually below
                name = os.path.split(addons_dir)[1]
                c = 0
                tmp = addons_dir + '_%d' % c
                while os.path.exists(tmp):
                    c += 1
                    tmp = addons_dir + '_%d' % c
                os.rename(addons_dir, tmp)
                os.mkdir(addons_dir)
                os.rename(tmp, join(addons_dir, name))

            addons_paths.append(addons_dir)
        return addons_paths

    def install(self):
        installed = []
        os.chdir(self.parts)

        # install server, webclient or gtkclient
        logger.info('Selected install type: %s', self.type)
        if self.type == 'downloadable':
            # download and extract
            if self.archive_path and not os.path.exists(self.archive_path):
                if self.offline:
                    raise IOError("%s not found, and offline mode requested" % self.archive_path)
                logger.info("Downloading %s ..." % self.url)
                msg = urllib.urlretrieve(self.url, self.archive_path)
                if msg[1].type == 'text/html':
                    os.unlink(self.archive_path)
                    raise IOError('Wanted version was not found: %s' % self.url)

            try:
                logger.info(u'Inspecting %s ...' % self.archive_path)
                tar = tarfile.open(self.archive_path)
                first = tar.next()
                # Everything that follows assumes all tarball members
                # are inside a directory with an expected name such
                # as openerp-6.1-1
                assert(first.isdir())
                extracted_name = first.name.split('/')[0]
                self.openerp_dir = join(self.parts, extracted_name)
                # protection against malicious tarballs
                assert(not os.path.isabs(extracted_name))
                assert(self.openerp_dir.startswith(self.parts))
            except (tarfile.TarError, IOError):
                raise IOError('The archive does not seem valid: ' +
                              repr(self.archive_path))

            if self.openerp_dir and not os.path.exists(self.openerp_dir):
                logger.info(u'Extracting %s ...' % self.archive_path)
                self.sandboxed_tar_extract(extracted_name, tar, first=first)
            tar.close()
        elif self.type == 'local':
            logger.info('Local directory chosen, nothing to do')
        elif self.type in ('bzr', 'hg', 'git', 'svn'):
            vcs_method = getattr(self, '%s_get_update' % self.type, None)
            vcs_method(self.openerp_dir, self.url, self.version_wanted)

        addons_paths = self.retrieve_addons()

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

        # configure addons_path option
        if addons_paths:
            if 'options.addons_path' not in self.options:
                self.options['options.addons_path'] = ''
            if self.version_detected[:3] == '6.0':
                self.options['options.addons_path'] += join(self.openerp_dir, 'bin', 'addons') + ','
            else:
                self.options['options.addons_path'] += join(self.openerp_dir, 'openerp', 'addons') + ','

            self.options['options.addons_path'] += ','.join(addons_paths)

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


class ServerRecipe(BaseRecipe):
    """Recipe for server install and config
    """
    archive_filenames = { '6.0': 'openerp-server-%s.tar.gz',
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


class WebClientRecipe(BaseRecipe):
    """Recipe for web client install and config
    """
    archive_filenames = {'6.0': 'openerp-web-%s.tar.gz'}
    requirements = ['setuptools']

    def _create_default_config(self):
        if self.version_detected[:3] == '6.0':
            shutil.copyfile(join(self.openerp_dir, 'doc', 'openerp-web.cfg'),
                            self.config_path)

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


class GtkClientRecipe(BaseRecipe):
    """Recipe for gtk client and config
    """
    archive_filenames = {'6.0': 'openerp-client-%s.tar.gz',
                        '6.1': 'openerp-client-%s.tar.gz' }
    requirements = []

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
            import options
            options.configmanager(self.config_path).save()

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

