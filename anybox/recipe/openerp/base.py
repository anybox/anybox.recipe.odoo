# coding: utf-8
from os.path import join, basename
import os, sys, urllib, tarfile, setuptools, logging, stat, imp
import shutil
import ConfigParser
import zc.recipe.egg

import httplib
import rfc822
from urlparse import urlparse
import vcs

logger = logging.getLogger(__name__)

def rfc822_time(h):
    """Parse RFC 2822-formatted http header and return a time int."""
    rfc822.mktime_tz(rfc822.parsedate_tz(h))

class BaseRecipe(object):
    """Base class for other recipes
    """

    default_dl_url = { '6.0': 'http://www.openerp.com/download/stable/source/',
                       '6.1': 'http://nightly.openerp.com/6.1/releases/'
                       }

    nightly_dl_url = {'6.1': 'http://nightly.openerp.com/6.1/nightly/src/',
                      }

    recipe_requirements = () # distribution required for the recipe itself
    requirements = () # requirements for what the recipe installs to run

    # Caching logic for the main OpenERP part (e.g, without addons)
    # Can be 'filename' or 'http-head'
    main_http_caching = 'filename'

    def __init__(self, buildout, name, options):
        self.requirements = list(self.requirements)
        self.recipe_requirements_path = []
        self.buildout, self.name, self.options = buildout, name, options
        self.b_options = self.buildout['buildout']
        self.buildout_dir = self.b_options['directory']
        # GR: would prefer lower() but doing as in 'zc.recipe.egg'
        self.offline = self.b_options['offline'] == 'true'

        clear_locks = options.get('vcs-clear-locks', '').lower()
        self.vcs_clear_locks = clear_locks == 'true'
        clear_retry = options.get('vcs-clear-retry', '').lower()
        self.clear_retry = clear_retry == 'true'

        self.downloads_dir = self.make_absolute(
            self.b_options.get('openerp-downloads-directory', 'downloads'))
        self.version_wanted = None  # from the buildout
        self.version_detected = None  # string from the openerp setup.py
        self.version_tuple = None # typed version suitable for comparisons
        self.parts = self.buildout['buildout']['parts-directory']
        self.addons = self.options.get('addons')
        self.openerp_dir = None
        self.url = None
        self.archive_filename = None
        self.archive_path = None # downloaded tar.gz

        if options.get('scripts') is None:
            options['scripts'] = ''

        self.etc = self.make_absolute('etc')
        self.bin_dir = self.buildout['buildout']['bin-directory']
        self.config_path = join(self.etc, self.name + '.cfg')
        for d in self.downloads_dir, self.etc:
            if not os.path.exists(d):
                logger.info('Created %s/ directory' % basename(d))
                os.mkdir(d)

        self.parse_version()

    def parse_version(self):
        """Set attributes describing retrieval actions to be taken.
        """

        self.version_wanted = self.options.get('version')
        if self.version_wanted is None:
            raise ValueError('You must specify the version')

        self.preinstall_version_check()

        version_split = self.version_wanted.split()

        if len(version_split) == 1:
            # version can be a simple version name, such as 6.1-1
            major_wanted = self.version_wanted[:3]
            pattern = self.archive_filenames[major_wanted]
            if pattern is None:
                raise ValueError(
                    'OpenERP version %r is not supported' % self.version_wanted)

            self.archive_filename = pattern % self.version_wanted
            self.type = 'downloadable'
            self.archive_path = join(self.downloads_dir, self.archive_filename)
            base_url = self.options.get(
                'base_url', self.default_dl_url[major_wanted])
            self.url = '/'.join((base_url.strip('/'), self.archive_filename))
            return

        # in all other cases, the first token is the type of version
        type_spec = version_split[0]
        if type_spec in ('local', 'path'):
            self.type = 'local'
            self.openerp_dir = join(self.buildout_dir, version_split[1])
        elif type_spec == 'url':
            self.type = 'downloadable'
            self.url = version_split[1]
            self.archive_filename = urlparse(self.url).path.split('/')[-1]
            self.archive_path = join(self.downloads_dir, self.archive_filename)
        elif type_spec == 'nightly':
            if len(version_split) != 3:
                raise ValueError(
                    "Unrecognized nightly version specification: "
                    "%r (expecting series, number) % version_split[1:]")
            series, self.version_wanted = version_split[1:]
            self.type = 'downloadable'
            if self.version_wanted == 'latest':
                self.main_http_caching = 'http-head'

            self.archive_filename = self.archive_nightly_filenames[series] % self.version_wanted
            self.archive_path = join(self.downloads_dir, self.archive_filename)
            base_url = self.options.get('base_url', self.nightly_dl_url[series])
            self.url = '/'.join((base_url.strip('/'), self.archive_filename))
        else:
            # VCS types
            if len(version_split) != 4:
                raise ValueError("Unrecognized version specification: %r "
                                 "(expecting type, url, target, revision for "
                                 "remote repository or explicit download) " % (
                        version_split))

            self.type, self.url, repo_dir, self.version_wanted = version_split
            self.openerp_dir = join(self.parts, repo_dir)

    def preinstall_version_check(self):
        """Perform version checks before any attempt to install.

        To be subclassed.
        """

    def install_recipe_requirements(self):
        """Install requirements for the recipe to run."""
        to_install = self.recipe_requirements
        eggs_option = os.linesep.join(to_install)
        eggs = zc.recipe.egg.Eggs(self.buildout, '', dict(eggs=eggs_option))
        ws = eggs.install()
        _, ws = eggs.working_set()
        self.recipe_requirements_paths = [ws.by_key[dist].location
                                          for dist in to_install]
        sys.path.extend(self.recipe_requirements_paths)

    def merge_requirements(self):
        """Merge eggs option with self.requirements."""
        if 'eggs' not in self.options:
            self.options['eggs'] = '\n'.join(self.requirements)
        else:
            self.options['eggs'] += '\n' + '\n'.join(self.requirements)

    def install_requirements(self):
        """Install egg requirements and scripts"""
        eggs = zc.recipe.egg.Scripts(self.buildout, '', self.options)
        ws = eggs.install()
        _, ws = eggs.working_set()
        self.ws = ws

    def read_openerp_setup(self):
        """Ugly method to extract requirements & version from ugly setup.py.

        Primarily designed for 6.0, but works with 6.1 as well.
        """
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
        sys.path.pop(0)
        setuptools.setup = old_setup

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

    def develop(self, src_directory):
        """Develop the specified source distribution.

        Any call to zc.recipe.eggs will use that developped version.
        develop() launches a subprocess, to which we need to forward
        the paths to requirements via PYTHONPATH
        """
        develop_dir = self.b_options['develop-eggs-directory']
        pythonpath_bak = os.getenv('PYTHONPATH')
        os.putenv('PYTHONPATH', ':'.join(self.recipe_requirements_paths))
        zc.buildout.easy_install.develop(self.openerp_dir, develop_dir)
        if pythonpath_bak is None:
            os.unsetenv('PYTHONPATH')
        else:
            os.putenv('PYTHONPATH', pythonpath_bak)

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
                repo_url, repo_dir, repo_rev = split[1:4]
                repo_dir = self.make_absolute(repo_dir)
                options = dict(offline=self.offline,
                               clear_locks=self.vcs_clear_locks)
                for k, v in self.options.items():
                    if k.startswith(repo_type + '-'):
                        options[k] = v

                vcs.get_update(repo_type, repo_dir, repo_url, repo_rev,
                               clear_retry=self.clear_retry,
                               **options)

            subdir = addons_options.get('subdir')
            addons_dir = subdir and join(repo_dir, subdir) or repo_dir

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

    def main_download(self):
        """HTTP download for main part of the software to self.archive_path.
        """
        if self.offline:
            raise IOError("%s not found, and offline mode requested" % self.archive_path)
        logger.info("Downloading %s ..." % self.url)

        try:
            msg = urllib.urlretrieve(self.url, self.archive_path)
            if msg[1].type == 'text/html':
                os.unlink(self.archive_path)
                raise LookupError(
                    'Wanted version %r not found on server (tried %s)' % (
                        self.version_wanted, self.url))

        except (tarfile.TarError, IOError):
            # GR: ContentTooShortError subclasses IOError
            os.unlink(self.archive_path)
            raise IOError('The archive does not seem valid: ' +
                          repr(self.archive_path))

    def is_stale_http_head(self):
        """Tell if the download is stale by doing a HEAD request.

        Assumes the correct date had been written upon download.
        This is the same system as in GNU Wget 1.12. It works even if
        the server does not implement conditional responses such as 304
        """
        stat = os.stat(self.archive_path)
        length, modified = stat.st_size, stat.st_mtime

        logger.info("Checking if %s if fresh wrt %s",
                    self.archive_path, self.url)
        parsed = urlparse(self.url)
        if parsed.scheme == 'https':
            cnx_cls = httplib.HTTPSConnection
        else:
            cnx_cls = httplib.HTTPConnection
        try:
            cnx = cnx_cls(parsed.netloc)
            cnx.request('HEAD', parsed.path) # TODO query ? fragment ?
            res = cnx.getresponse()
        except IOError:
            return True

        if res.status != 200:
            return True

        if int(res.getheader('Content-Length')) != length:
            return True

        head_modified = res.getheader('Last-Modified')
        logger.debug("Last-modified from HEAD request: %s", head_modified)
        if rfc822_time(head_modified) > modified:
            return True

        logger.info("No need to re-download %s", self.archive_path)

    def install(self):
        self.openerp_installed = []
        os.chdir(self.parts)

        # install server, webclient or gtkclient
        logger.info('Selected install type: %s', self.type)
        if self.type == 'downloadable':
            # download if needed
            if ((self.archive_path  and not os.path.exists(self.archive_path))
                 or (self.main_http_caching == 'http-head'
                     and self.is_stale_http_head())):
                self.main_download()

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

            logger.info("Cleaning existing %s", self.openerp_dir)
            if os.path.exists(self.openerp_dir):
                shutil.rmtree(self.openerp_dir)
            logger.info(u'Extracting %s ...' % self.archive_path)
            self.sandboxed_tar_extract(extracted_name, tar, first=first)
            tar.close()
        elif self.type == 'local':
            logger.info('Local directory chosen, nothing to do')
        else:
            vcs.get_update(self.type, self.openerp_dir, self.url,
                           self.version_wanted, offline=self.offline,
                           clear_retry=self.clear_retry)

        addons_paths = self.retrieve_addons()
        for path in addons_paths:
            assert os.path.isdir(path), (
                "Not a directory: %r (aborting)" % path)

        self.install_recipe_requirements()
        os.chdir(self.openerp_dir) # GR probably not needed any more
        self.read_openerp_setup()
        if self.type == 'downloadable' and self.version_wanted == 'latest':
            logger.warn("Detected version: %s, you may want to fix that "
                        "in your config file for replayability",
                        self.version_detected)
        is_60 = self.version_detected[:3] == '6.0'
        # configure addons_path option
        if addons_paths:
            if 'options.addons_path' not in self.options:
                self.options['options.addons_path'] = ''
            if is_60:
                self.options['options.addons_path'] += join(self.openerp_dir, 'bin', 'addons') + ','
            else:
                self.options['options.addons_path'] += join(self.openerp_dir, 'openerp', 'addons') + ','

            self.options['options.addons_path'] += ','.join(addons_paths)
        elif is_60:
            self._60_default_addons_path()

        if is_60:
            self._60_fix_root_path()

        # add openerp paths into the extra-paths
        if (self.version_detected.startswith('7')
            or self.version_detected.startswith('6.2')): # TODO use a tuple !
            paths = [self.openerp_dir,
                     join(self.openerp_dir, 'addons')] # TODO necessary ?
        else:
            paths = [join(self.openerp_dir, 'bin'),
                     join(self.openerp_dir, 'bin', 'addons')]
        paths.append(self.options.get('extra-paths', ''))
        self.options['extra-paths'] = os.linesep.join(paths)

        if self.version_detected is None:
            raise EnvironmentError('Version of OpenERP could not be detected')
        self.merge_requirements()
        self.install_requirements()
        self._install_startup_scripts()

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

        return self.openerp_installed

    def _install_script(self, name, content):
        """Install and register a script with prescribed name and content.

        Return the script path
        """
        path = join(self.bin_dir, name)
        f = open(path, 'w')
        f.write(content)
        f.close()
        os.chmod(path, stat.S_IRWXU)
        self.openerp_installed.append(path)
        return path

    def _install_startup_scripts(self):
        raise NotImplementedError

    def _create_default_config(self):
        raise NotImplementedError

    update = install

    def _60_fix_root_path(self):
        """Correction of root path for OpenERP 6.0 pure python install

        Actual implementation is up to subclasses
        """

    def _60_default_addons_path(self):
        """Set the default addons patth for OpenERP 6.0 pure python install

        Actual implementation is up to subclasses
        """
