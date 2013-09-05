# coding: utf-8
from os.path import join, basename
import os
import sys
import urllib
import tarfile
import setuptools
import logging
import stat
import imp
import shutil
import ConfigParser
import distutils.core
import pkg_resources
try:
    from collections import OrderedDict
except ImportError:  # Python < 2.7
    from ordereddict import OrderedDict  # noqa
from zc.buildout.easy_install import MissingDistribution
from zc.buildout import UserError
from zc.buildout.easy_install import VersionConflict
import zc.recipe.egg

import httplib
import rfc822
from urlparse import urlparse
from . import vcs
from . import utils

logger = logging.getLogger(__name__)


def rfc822_time(h):
    """Parse RFC 2822-formatted http header and return a time int."""
    rfc822.mktime_tz(rfc822.parsedate_tz(h))


class MainSoftware(object):
    """Placeholder to represent the main software instead of an addon location.
    """

    def __str__(self):
        return 'Main Software'

main_software = MainSoftware()

GP_VCS_EXTEND_DEVELOP = 'vcs-extend-develop'


class BaseRecipe(object):
    """Base class for other recipes.

    It implements notably fetching of the main software part plus addons.
    The ``sources`` attributes is a dict storing how to fetch the main software
    part and specified addons. It has the following structure:

        local path -> (type, location_spec, options).

        where local path is the ``main_software`` object for the main software
        part, and otherwise a local path to an addons container.

        type can be
            - 'local'
            - 'downloadable'
            - one of the supported vcs

        location_spec is, depending on the type, a tuple specifying how to
        fetch : (url, None), or (vcs_url, vcs_revision) or None

        addons options are typically used to specify that the addons directory
        is actually a subdir of the specified one.

    """

    default_dl_url = {'6.0': 'http://nightly.openerp.com/6.0/6.0/',
                      '6.1': 'http://nightly.openerp.com/6.1/releases/',
                      '7.0': 'http://nightly.openerp.com/7.0/releases/',
                      '5.0': 'http://nightly.openerp.com/old/openerp-5/',
                      }

    nightly_dl_url = {'6.0': 'http://nightly.openerp.com/6.0/6.0/',
                      '6.1': 'http://nightly.openerp.com/6.1/nightly/src/',
                      '7.0': 'http://nightly.openerp.com/7.0/nightly/src/',
                      'trunk': 'http://nightly.openerp.com/trunk/nightly/src/',
                      }

    recipe_requirements = ()  # distribution required for the recipe itself
    recipe_requirements_paths = ()  # a default value is useful in unit tests
    requirements = ()  # requirements for what the recipe installs to run
    soft_requirements = ()  # subset of requirements that's not necessary
    addons_paths = ()

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
        # (later) the standard way for all booleans is to use
        # options.query_bool() or get_bool(), but it doesn't lower() at all
        self.offline = self.b_options['offline'] == 'true'
        self.clean = options.get('clean') == 'true'
        clear_locks = options.get('vcs-clear-locks', '').lower()
        self.vcs_clear_locks = clear_locks == 'true'
        clear_retry = options.get('vcs-clear-retry', '').lower()
        self.clear_retry = clear_retry == 'true'

        # same as in zc.recipe.eggs
        self.extra_paths = [
            join(self.buildout_dir, p.strip())
            for p in self.options.get('extra-paths', '').split(os.linesep)
            if p.strip()
        ]
        self.options['extra-paths'] = os.linesep.join(self.extra_paths)

        self.downloads_dir = self.make_absolute(
            self.b_options.get('openerp-downloads-directory', 'downloads'))
        self.version_wanted = None  # from the buildout
        self.version_detected = None  # string from the openerp setup.py
        self.parts = self.buildout['buildout']['parts-directory']
        self.openerp_dir = None
        self.archive_filename = None
        self.archive_path = None  # downloaded tar.gz

        if options.get('scripts') is None:
            options['scripts'] = ''

        # a dictionnary of messages to display in case a distribution is
        # not installable.
        self.missing_deps_instructions = {
            'PIL': ("You don't need to require it for OpenERP any more, since "
                    "the recipe automatically adds a dependency to Pillow. "
                    "If you really need it for other reasons, installing it "
                    "system-wide is a good option. "),
        }

        self.openerp_installed = []

        self.etc = self.make_absolute(options.get('etc-directory', 'etc'))
        self.bin_dir = self.buildout['buildout']['bin-directory']
        self.config_path = join(self.etc, self.name + '.cfg')
        for d in self.downloads_dir, self.etc:
            if not os.path.exists(d):
                logger.info('Created %s/ directory' % basename(d))
                os.mkdir(d)

        self.sources = OrderedDict()
        self.parse_addons(options)
        self.parse_version()
        self.parse_revisions(options)

    def parse_version(self):
        """Set the main software in ``sources`` and related attributes.
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
                    'OpenERP version %r'
                    'is not supported' % self.version_wanted)

            self.archive_filename = pattern % self.version_wanted
            self.archive_path = join(self.downloads_dir, self.archive_filename)
            base_url = self.options.get(
                'base_url', self.default_dl_url[major_wanted])
            self.sources[main_software] = (
                'downloadable',
                ('/'.join((base_url.strip('/'), self.archive_filename)), None))
            return

        # in all other cases, the first token is the type of version
        type_spec = version_split[0]
        if type_spec in ('local', 'path'):
            self.openerp_dir = join(self.buildout_dir, version_split[1])
            self.sources[main_software] = ('local', None)
        elif type_spec == 'url':
            url = version_split[1]
            self.archive_filename = urlparse(url).path.split('/')[-1]
            self.archive_path = join(self.downloads_dir, self.archive_filename)
            self.sources[main_software] = ('downloadable', (url, None))
        elif type_spec == 'nightly':
            if len(version_split) != 3:
                raise ValueError(
                    "Unrecognized nightly version specification: "
                    "%r (expecting series, number) % version_split[1:]")
            self.nightly_series, self.version_wanted = version_split[1:]
            type_spec = 'downloadable'
            if self.version_wanted == 'latest':
                self.main_http_caching = 'http-head'
            series = self.nightly_series
            self.archive_filename = (
                self.archive_nightly_filenames[series] % self.version_wanted)
            self.archive_path = join(self.downloads_dir, self.archive_filename)
            base_url = self.options.get('base_url',
                                        self.nightly_dl_url[series])
            self.sources[main_software] = (
                'downloadable',
                ('/'.join((base_url.strip('/'), self.archive_filename)), None))
        else:
            # VCS types
            type_spec, url, repo_dir, self.version_wanted = version_split[0:4]
            options = dict(opt.split('=') for opt in version_split[4:])
            self.openerp_dir = join(self.parts, repo_dir)
            self.sources[main_software] = (type_spec,
                                           (url, self.version_wanted), options)

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
        """Install egg requirements and scripts.

        If some distributions are known as soft requirements, will retry
        without them
        """
        while True:
            missing = None
            eggs = zc.recipe.egg.Scripts(self.buildout, '', self.options)
            try:
                eggs.install()
            except MissingDistribution, exc:
                missing = exc.data[0].project_name
            except VersionConflict:
                raise
            except UserError, exc:  # zc.buildout >= 2.0
                missing = exc.message.split(os.linesep)[0].split()[-1]

            if missing is not None:
                msg = self.missing_deps_instructions.get(missing)
                if msg is None:
                    raise
                logger.error("Could not find %r. " + msg, missing)
                # GR this condition won't be enough in case of version
                # conditions in requirement
                if missing not in self.soft_requirements:
                    sys.exit(1)
                else:
                    attempted = self.options['eggs'].split(os.linesep)
                    self.options['eggs'] = os.linesep.join(
                        [egg for egg in attempted if egg != missing])
            else:
                break

        self.eggs_reqs, self.eggs_ws = eggs.working_set()
        self.ws = self.eggs_ws

    def apply_version_dependent_decisions(self):
        """Store some booleans depending on detected version.

        To be refined by subclasses.
        """
        pass

    @property
    def major_version(self):
        detected = self.version_detected
        if detected is None:
            return None
        return utils.major_version(detected)

    def read_release(self):
        """Try and read the release.py file directly.

        Should be used only if reading setup.py failed, which happens
        with OpenERP 5.0
        """
        with open(join(self.openerp_dir, 'bin', 'release.py'), 'rb') as f:
            mod = imp.load_module('release', f, 'release.py',
                                  ('.py', 'r', imp.PY_SOURCE))
        self.version_detected = mod.version

    def read_openerp_setup(self):
        """Ugly method to extract requirements & version from ugly setup.py.

        Primarily designed for 6.0, but works with 6.1 as well.
        """
        old_setup = setuptools.setup
        old_distutils_setup = distutils.core.setup  # 5.0 directly imports this

        def new_setup(*args, **kw):
            self.requirements.extend(kw.get('install_requires', ()))
            self.version_detected = kw['version']
        setuptools.setup = new_setup
        distutils.core.setup = new_setup
        sys.path.insert(0, '.')
        with open(join(self.openerp_dir, 'setup.py'), 'rb') as f:
            saved_argv = sys.argv
            sys.argv = ['setup.py', 'develop']
            try:
                imp.load_module('setup', f, 'setup.py',
                                ('.py', 'r', imp.PY_SOURCE))
            except SystemExit as exception:
                msg = exception.message
                if not isinstance(msg, int) and 'dsextras' in msg:
                    raise EnvironmentError(
                        'Please first install PyGObject and PyGTK !')
                else:
                    try:
                        self.read_release()
                    except Exception as exc:
                        raise EnvironmentError(
                            'Problem while reading OpenERP release.py: '
                            + exc.message)
            except ImportError, exception:
                if 'babel' in exception.message:
                    raise EnvironmentError(
                        'OpenERP setup.py has an unwanted import Babel.\n'
                        '=> First install Babel on your system or '
                        'virtualenv :(\n'
                        '(sudo aptitude install python-babel, '
                        'or pip install babel)')
                else:
                    raise exception
            except Exception, exception:
                raise EnvironmentError('Problem while reading OpenERP '
                                       'setup.py: ' + exception.message)
            finally:
                sys.argv = saved_argv
        sys.path.pop(0)
        setuptools.setup = old_setup
        distutils.core.setup = old_distutils_setup
        self.apply_version_dependent_decisions()

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
        It is taken for granted that this first member has already been
        checked.
        """

        if first is not None:
            tarfile.extract(first)

        for tinfo in tarfile:
            if tinfo.name.startswith(sandbox + '/'):
                tarfile.extract(tinfo)
            else:
                logger.warn('Tarball member %r is outside of %r. Ignored.',
                            tinfo, sandbox)

    def _produce_setup_without_pil(self, src_directory):
        """Create a copy of setup.py without PIL and return a path to it."""

        new_setup_path = join(src_directory, 'setup.nopil.py')
        with open(join(src_directory, 'setup.py')) as inp:
            setup_str = inp.read()
        with open(new_setup_path, 'w') as out:
            out.write(setup_str.replace("'PIL',", ''))
        return new_setup_path

    def develop(self, src_directory, setup_has_pil=False):
        """Develop the specified source distribution.

        Any call to zc.recipe.eggs will use that developped version.
        develop() launches a subprocess, to which we need to forward
        the paths to requirements via PYTHONPATH.
        If setup_has_pil is True, an altered version of setup that does not
        require it is produced to perform the develop.
        """
        logger.debug("Developing %r", src_directory)
        develop_dir = self.b_options['develop-eggs-directory']
        pythonpath_bak = os.getenv('PYTHONPATH')
        os.putenv('PYTHONPATH', ':'.join(self.recipe_requirements_paths))

        if setup_has_pil:
            setup = self._produce_setup_without_pil(src_directory)
        else:
            setup = src_directory

        try:
            zc.buildout.easy_install.develop(setup, develop_dir)
        finally:
            if setup_has_pil:
                os.unlink(setup)

        if pythonpath_bak is None:
            os.unsetenv('PYTHONPATH')
        else:
            os.putenv('PYTHONPATH', pythonpath_bak)

    def parse_addons(self, options):
        """Parse the addons options into the ``sources`` attribute.

        See ``BaseRecipe`` docstring for details about the ``sources`` dict.
        """

        for line in options.get('addons', '').split(os.linesep):
            split = line.split()
            if not split:
                return
            loc_type = split[0]
            spec_len = 2 if loc_type == 'local' else 4

            options = dict(opt.split('=') for opt in split[spec_len:])
            if loc_type == 'local':
                addons_dir = split[1]
                location_spec = None
            else:  # vcs
                repo_url, addons_dir, repo_rev = split[1:4]
                location_spec = (repo_url, repo_rev)

            addons_dir = addons_dir.rstrip('/')  # trailing / can be harmful
            self.sources[addons_dir] = (loc_type, location_spec, options)

    def parse_revisions(self, options):
        """Parse revisions options and update the ``sources`` attribute.

        It is assumed that ``sources`` has already been populated, and
        notably has a main_software part.
        This allows for easy fixing of revisions in an extension buildout
        """
        for line in options.get('revisions', '').split(os.linesep):
            # GR inline comment should have not gone through, but sometimes
            # does (see lp:1130590). This below does not exactly conform to
            # spec http://docs.python.org/2/library/configparser.html
            # (we don't check for whitespace before separator), but is good
            # enough in this case.
            line = line.split(';', 1)[0].strip()
            if not line:
                continue

            split = line.split()
            if len(split) > 2:
                raise ValueError("Invalid revisions line: %r" % line)

            # addon or main software
            if len(split) == 2:
                local_path = split[0]
            else:
                local_path = main_software
            revision = split[-1]

            source = self.sources.get(local_path)
            if source is None:  # considered harmless for now
                logger.warn("Ignoring attempt to fix revision on unknown "
                            "source %r. You may have a leftover to clean",
                            local_path)
                continue

            if source[0] in ('downloadable', 'local'):
                raise ValueError("In revision line %r : can't fix a revision "
                                 "for non-vcs source" % line)

            logger.info("%s will be on revision %r", local_path, revision)
            self.sources[local_path] = ((source[0], (source[1][0], revision))
                                        + source[2:])

    def retrieve_addons(self):
        """Parse the addons option line, download and return a list of paths.

        syntax: repo_type repo_url repo_dir repo_rev [options]
              or an absolute or relative path
        options are themselves in the key=value form
        """
        self.addons_paths = []
        for local_dir, source_spec in self.sources.items():
            if local_dir is main_software:
                continue

            loc_type, loc_spec, addons_options = source_spec
            local_dir = self.make_absolute(local_dir)
            options = dict(offline=self.offline,
                           clear_locks=self.vcs_clear_locks,
                           clean=self.clean)
            options.update(addons_options)

            if loc_type != 'local':
                for k, v in self.options.items():
                    if k.startswith(loc_type + '-'):
                        options[k] = v

                repo_url, repo_rev = loc_spec
                vcs.get_update(loc_type, local_dir, repo_url, repo_rev,
                               clear_retry=self.clear_retry,
                               **options)
            elif self.clean:
                utils.clean_object_files(local_dir)

            subdir = addons_options.get('subdir')
            addons_dir = join(local_dir, subdir) if subdir else local_dir

            manifest = os.path.join(addons_dir, '__openerp__.py')
            manifest_pre_v6 = os.path.join(addons_dir, '__terp__.py')
            if os.path.isfile(manifest) or os.path.isfile(manifest_pre_v6):
                if loc_type == 'local':
                    raise ValueError(
                        "Local addons line %r should refer to a directory "
                        "containing addons, not to a standalone addon. "
                        "The recipe can perform automatic creation of "
                        "intermediate directories for VCS cases only"
                        % addons_dir)
                # repo is a single addon, put it actually below
                name = os.path.split(addons_dir)[1]
                c = 0
                tmp = addons_dir + '_%d' % c
                while os.path.exists(tmp):
                    c += 1
                    tmp = addons_dir + '_%d' % c
                os.rename(addons_dir, tmp)
                os.mkdir(addons_dir)
                new_dir = join(addons_dir, name)
                os.rename(tmp, new_dir)
            self.addons_paths.append(addons_dir)

    def main_download(self):
        """HTTP download for main part of the software to self.archive_path.
        """
        if self.offline:
            raise IOError("%s not found, and offline "
                          "mode requested" % self.archive_path)
        url = self.sources[main_software][1][0]
        logger.info("Downloading %s ..." % url)

        try:
            msg = urllib.urlretrieve(url, self.archive_path)
            if msg[1].type == 'text/html':
                os.unlink(self.archive_path)
                raise LookupError(
                    'Wanted version %r not found on server (tried %s)' % (
                        self.version_wanted, url))

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
        archivestat = os.stat(self.archive_path)
        length, modified = archivestat.st_size, archivestat.st_mtime

        url = self.sources[main_software][1][0]
        logger.info("Checking if %s if fresh wrt %s",
                    self.archive_path, url)
        parsed = urlparse(url)
        if parsed.scheme == 'https':
            cnx_cls = httplib.HTTPSConnection
        else:
            cnx_cls = httplib.HTTPConnection
        try:
            cnx = cnx_cls(parsed.netloc)
            cnx.request('HEAD', parsed.path)  # TODO query ? fragment ?
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

    def retrieve_main_software(self):
        """install server, webclient or gtkclient."""

        source = self.sources[main_software]
        type_spec = source[0]
        logger.info('Selected install type: %s', type_spec)
        if type_spec == 'local':
            logger.info('Local directory chosen, nothing to do')
            if self.clean:
                utils.clean_object_files(self.openerp_dir)
        elif type_spec == 'downloadable':
            # download if needed
            if ((self.archive_path and not os.path.exists(self.archive_path))
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
        else:
            url, rev = source[1]
            options = dict((k, v) for k, v in self.options.iteritems()
                           if k.startswith(type_spec + '-'))
            options.update(source[2])
            if self.clean:
                options['clean'] = True
            vcs.get_update(type_spec, self.openerp_dir, url, rev,
                           offline=self.offline,
                           clear_retry=self.clear_retry, **options)

    def _register_extra_paths(self):
        """Add openerp paths into the extra-paths (used in scripts' sys.path).
        """
        extra = self.extra_paths
        if self.major_version >= (6, 2):
            # TODO still necessary ?
            extra.extend((self.openerp_dir,
                         join(self.openerp_dir, 'addons')))
        else:
            extra.extend((join(self.openerp_dir, 'bin'),
                          join(self.openerp_dir, 'bin', 'addons')))
        self.options['extra-paths'] = os.linesep.join(extra)

    def install(self):
        os.chdir(self.parts)

        freeze_to = self.options.get('freeze-to')
        extract_downloads_to = self.options.get('extract-downloads-to')

        if ((freeze_to is not None or extract_downloads_to is not None)
                and not self.offline):
            raise ValueError("To freeze a part, you must run offline "
                             "so that there's no modification from what "
                             "you just tested. Please rerun with -o.")

        if extract_downloads_to is not None and freeze_to is None:
            freeze_to = os.path.join(extract_downloads_to,
                                     'extracted_from.cfg')

        self.retrieve_main_software()
        self.retrieve_addons()

        self.install_recipe_requirements()
        os.chdir(self.openerp_dir)  # GR probably not needed any more
        self.read_openerp_setup()

        if (self.sources[main_software][0] == 'downloadable'
                and self.version_wanted == 'latest'):
            self.nightly_version = self.version_detected.split('-', 1)[1]
            logger.warn("Detected 'nightly latest version', you may want to "
                        "fix it in your config file for replayability: \n    "
                        "version = " + self.dump_nightly_latest_version())

        self.finalize_addons_paths()
        self._register_extra_paths()

        if self.version_detected is None:
            raise EnvironmentError('Version of OpenERP could not be detected')
        self.merge_requirements()
        self.install_requirements()

        self._install_startup_scripts()

        # create the config file
        if os.path.exists(self.config_path):
            os.remove(self.config_path)
        logger.info('Creating config file: %s',
                    os.path.relpath(self.config_path, self.buildout_dir))
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

        if extract_downloads_to:
            self.extract_downloads_to(extract_downloads_to)
        if freeze_to:
            self.freeze_to(freeze_to)
        return self.openerp_installed

    def dump_nightly_latest_version(self):
        """After download/analysis of 'nightly latest', give equivalent spec.
        """
        return ' '.join((self.nightly_series, 'nightly', self.nightly_version))

    def freeze_to(self, out_config_path):
        """Create an extension buildout freezing current revisions & versions.
        """

        logger.info("Freezing part %r to config file %r", self.name,
                    out_config_path)
        out_conf = ConfigParser.ConfigParser()

        frozen = getattr(self.buildout, '_openerp_recipe_frozen', None)
        if frozen is None:
            frozen = self.buildout._openerp_recipe_frozen = set()

        if out_config_path in frozen:
            # read configuration started by other recipe
            out_conf.read(self.make_absolute(out_config_path))
        else:
            self._prepare_frozen_buildout(out_conf)

        self._freeze_egg_versions(out_conf, 'versions')

        out_conf.add_section(self.name)
        addons_option = []
        self.local_modifications = []
        for local_path, source in self.sources.items():
            source_type = source[0]
            if source_type == 'local':
                continue

            if local_path is main_software:
                if source_type == 'downloadable':
                    self._freeze_downloadable_main_software(out_conf)
                else:  # vcs
                    abspath = self.openerp_dir
                    self.cleanup_openerp_dir()
            else:
                abspath = self.make_absolute(local_path)

            if source_type == 'downloadable':
                continue

            revision = self._freeze_vcs_source(source_type, abspath)
            if local_path is main_software:
                addons_option.insert(0, '%s  ; main software part' % revision)
                # actually, that comment will be lost if this is not the
                # last part (dropped upon reread)
            else:
                addons_option.append(' '.join((local_path, revision)))

        if addons_option:
            out_conf.set(self.name, 'revisions',
                         os.linesep.join(addons_option))
        if self.local_modifications:

            logger.error(
                "Uncommitted changes and/or untracked files in: %s"
                "Unsafe to freeze. Please commit or revert and test again !",
                os.linesep.join(
                    ['', ''] + ['   - ' + p
                                for p in self.local_modifications] + ['', '']))

            sys.exit(17)  # GR I like that number

        with open(self.make_absolute(out_config_path), 'w') as out:
            out_conf.write(out)
        frozen.add(out_config_path)

    def _get_gp_vcs_develops(self):
        """Return a tuple of (raw, parsed) vcs-extends-develop specifications.
        """
        lines = self.b_options.get(
            GP_VCS_EXTEND_DEVELOP)
        if not lines:
            return ()

        try:
            import pip.req
        except ImportError:
            logger.error("You have vcs-extends-develop distributions "
                         "but pip is not available. That means that "
                         "gp.vcsdevelop is not properly installed. Did "
                         "you ever run that buildout ?")
            raise

        return tuple((line, pip.req.parse_editable(line))
                     for line in lines.split(os.linesep) if line)

    def _prepare_frozen_buildout(self, conf):
        """Create the 'buildout' section in conf."""
        conf.add_section('buildout')
        conf.set('buildout', 'extends', self.buildout_cfg_name())
        conf.add_section('versions')
        conf.set('buildout', 'versions', 'versions')

        # freezing for gp.vcsdevelop
        extends = []
        for raw, parsed in self._get_gp_vcs_develops():
            local_path = parsed[0]
            hash_split = raw.rsplit('#')
            url = hash_split[0]
            url = url.rsplit('@', 1)[0]
            vcs_type = url.split('+', 1)[0]
            # vcs-develop process adds .egg-info file (often forgotten in VCS
            # ignore files) and changes setup.cfg.
            # For now we'll have to allow local modifications.
            revision = self._freeze_vcs_source(vcs_type,
                                               self.make_absolute(local_path),
                                               allow_local_modification=True)
            extends.append('%s@%s#%s' % (url, revision, hash_split[1]))

        conf.set('buildout', GP_VCS_EXTEND_DEVELOP, os.linesep.join(extends))

    def _freeze_downloadable_main_software(self, conf):
        """If needed, sets the main version option in ConfigParser.

        Currently does not dump the fully resolved URL, since future
        reproduction may be better done with another URL base holding archived
        old versions : it's better to let tomorrow logic handle that
        from higher level information.
        """

        if self.version_wanted == 'latest':
            conf.set(self.name, 'version', self.dump_nightly_latest_version())

    def _freeze_egg_versions(self, conf, section, exclude=()):
        """Update a ConfigParser section with current working set egg versions.
        """
        versions = dict((name, conf.get(section, name))
                        for name in conf.options(section))
        versions.update((name, egg.version)
                        for name, egg in self.ws.by_key.items()
                        if name not in exclude
                        and egg.precedence != pkg_resources.DEVELOP_DIST
                        )
        for name, version in versions.items():
            conf.set(section, name, version)

        # forbidding picked versions if this zc.buildout supports it right away
        # i.e. we are on zc.buildout >= 2.0
        allow_picked = self.options.get('freeze-allow-picked-versions', '')
        if allow_picked.strip() == 'false':
            pick_opt = 'allow-picked-versions'
            if pick_opt in self.b_options:
                conf.set('buildout', pick_opt, 'false')

    def _freeze_vcs_source(self, vcs_type, abspath,
                           allow_local_modification=False):
        """Return the current revision for that VCS source."""

        repo_cls = vcs.SUPPORTED[vcs_type]
        abspath = repo_cls.fix_target(abspath)
        repo = repo_cls(abspath, '')  # no need of remote URL

        if not allow_local_modification and repo.uncommitted_changes():
            self.local_modifications.append(abspath)

        parents = repo.parents()
        if len(parents) > 1:
            self.local_modifications.append(abspath)

        return parents[0]

    def extract_downloads_to(self, target_dir, outconf_name='release.cfg'):
        """Extract anything that has been downloaded to target_dir.

        This doesn't copy intermediary buildout configurations nor local parts.
        In the purpose of making a self-contained and offline playable archive,
        these are assumed to be already taken care of.
        """
        logger.info("Extracting part %r to directory %r and config file %r "
                    "therein.", self.name, target_dir, outconf_name)
        target_dir = self.make_absolute(target_dir)
        out_conf = ConfigParser.ConfigParser()

        all_extracted = getattr(self.buildout, '_openerp_recipe_extracted',
                                None)
        if all_extracted is None:
            all_extracted = self.buildout._openerp_recipe_extracted = {}
        out_config_path = join(target_dir, outconf_name)

        # GR TODO this will fail if same target dir has been used with
        # a different outconf_name
        if target_dir in all_extracted:
            # read configuration started by other recipe
            out_conf.read(out_config_path)
            extracted = all_extracted[target_dir]
        else:
            self._prepare_extracted_buildout(out_conf, target_dir)
            extracted = all_extracted[target_dir] = set()

        self._freeze_egg_versions(out_conf, 'versions')
        self._extract_sources(out_conf, target_dir, extracted)
        with open(out_config_path, 'w') as out:
            out_conf.write(out)

    def _extract_sources(self, out_conf, target_dir, extracted):
        """Core extraction method.

        out_conf is a ConfigParser instance to write to
        extracted is a technical set used to know what targets have already
        been written by previous parts and store for subsequent ones.
        """

        if not os.path.exists(target_dir):
            os.mkdir(target_dir)

        out_conf.add_section(self.name)
        addons_option = []
        for local_path, source in self.sources.items():
            source_type = source[0]
            if local_path is main_software:
                rel_path = self._extract_main_software(source_type, target_dir,
                                                       extracted)
                out_conf.set(self.name, 'version', 'local ' + rel_path)
                continue

            addons_line = ['local', local_path]
            addons_line.extend('%s=%s' % (opt, val)
                               for opt, val in source[2].items())
            addons_option.append(' '.join(addons_line))

            abspath = self.make_absolute(local_path)
            if source_type == 'downloadable':
                shutil.copytree(abspath,
                                os.path.join(target_dir, local_path))
            elif source_type != 'local':  # vcs
                self._extract_vcs_source(source_type, abspath, target_dir,
                                         local_path, extracted)

        out_conf.set(self.name, 'addons', os.linesep.join(addons_option))
        if self.options.get('revisions'):
            out_conf.set(self.name, 'revisions', '')
            # GR hacky way to make a comment for a void value. Indeed,
            # "revisions = ; comment" is not recognized as an inline comment
            # because of overall stripping and a need for whitespace before
            # the semicolon (sigh)
            out_conf.set(self.name, '; about revisions',
                         "the extended buildout '%s' uses the 'revisions' "
                         "option. The present override disables it "
                         "because it makes no sense after extraction and "
                         "replacement by the "
                         "'local' scheme" % self.buildout_cfg_name())

    def _extract_vcs_source(self, vcs_type, repo_path, target_dir, local_path,
                            extracted):
        """Extract a VCS source.

        The extracted argument is a set of previously extracted targets.
        This is because some VCS will refuse an empty directory (bzr does)
        """

        repo_path = self.make_absolute(repo_path)
        repo_cls = vcs.SUPPORTED[vcs_type]
        fixed_repo_path = repo_cls.fix_target(repo_path)
        target_path = os.path.join(target_dir, local_path)
        if fixed_repo_path != repo_path:
            # again the problem of shifts, temp lame solution
            split = os.path.split(fixed_repo_path)
            assert split[0] == repo_path
            target_path = os.path.join(target_path, split[1])

        utils.mkdirp(target_path)
        if target_path in extracted:
            return

        repo = repo_cls(fixed_repo_path, '')  # no need of remote URL
        repo.archive(target_path)
        extracted.add(target_path)

    def _extract_main_software(self, source_type, target_dir, extracted):
        """Extract the main software to target_dir and return relative path.

        As this is for extract_downloads_to, local main software is not
        extracted (supposed to be taken care of by the tool that does the
        archival of buildout dir itself).

        The extracted set avoids extracting twice to same target (refused
        by some VCSes anyway)
        """
        if not self.openerp_dir.startswith(self.buildout_dir):
            raise RuntimeError(
                "Main openerp directory %r outside of buildout "
                "directory, don't know how to handle that" % self.openerp_dir)

        local_path = self.openerp_dir[len(self.buildout_dir + os.sep):]
        target_path = join(target_dir, local_path)
        if target_path in extracted:
            return local_path

        if source_type == 'downloadable':
            shutil.copytree(self.openerp_dir, target_path)
        elif source_type != 'local':  # see docstring for 'local'
            self._extract_vcs_source(source_type, self.openerp_dir, target_dir,
                                     local_path, extracted)
        return local_path

    def _prepare_extracted_buildout(self, conf, target_dir):
        """Create the 'buildout' section in ``conf``.

        Also takes care of gp.vcsdevelop driven distributions.

        In most cases, at this stage, gp.vcsdevelop and regular develop
        distributions are expressed with absolute paths. This method will make
        them local in the destination ``conf``

        Regular develop distributions pointing outside of buildout directory
        are kept as is, assuming this has been specified in absolute form
        in the config file, hence to some resources that are outside of
        the recipe control, that are therefore expected to be deployed before
        hand on target systems.
        """
        conf.add_section('buildout')
        conf.set('buildout', 'extends', self.buildout_cfg_name())
        conf.add_section('versions')
        conf.set('buildout', 'versions', 'versions')

        develops = set(self.b_options.get('develop', '').split(os.linesep))

        extracted = set()
        for raw, parsed in self._get_gp_vcs_develops():
            local_path = parsed[0]
            abs_path = self.make_absolute(local_path)
            vcs_type = raw.split('+', 1)[0]
            self._extract_vcs_source(vcs_type, abs_path,
                                     target_dir, local_path, extracted)
            develops.add(abs_path)  # looks silly, but better for uniformity

        bdir = os.path.join(self.buildout_dir, '')
        conf.set('buildout', 'develop',
                 os.linesep.join(d[len(bdir):] if d.startswith(bdir) else d
                                 for d in develops))
        conf.set('buildout', GP_VCS_EXTEND_DEVELOP, '')

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
        """Set the default addons path for OpenERP 6.0 pure python install

        Actual implementation is up to subclasses
        """

    def _default_addons_path(self):
        """Set the default addons path for OpenERP > 6.0 pure python install

        Actual implementation is up to subclasses
        """

    def finalize_addons_paths(self, check_existence=True):
        """Add implicit paths and serialize in the addons_path option.

        if check_existence is True, all the paths will be checked for
        existence.
        """
        opt_key = 'options.addons_path'
        if opt_key in self.options:
            raise UserError("In part %r, direct use of %s is prohibited. "
                            "please use addons lines with type 'local' "
                            "instead." % (self.name, opt_key))

        if self.major_version <= (6, 0):
            base_addons = join(self.openerp_dir, 'bin', 'addons')
        else:
            base_addons = join(self.openerp_dir, 'openerp', 'addons')
        if os.path.exists(base_addons):
            self.addons_paths.append(base_addons)

        if check_existence:
            for path in self.addons_paths:
                assert os.path.isdir(path), (
                    "Not a directory: %r (aborting)" % path)

        self.options['options.addons_path'] = ','.join(self.addons_paths)
        if self.major_version <= (6, 0):
            self._60_fix_root_path()

    def cleanup_openerp_dir(self):
        """Revert local modifications that have been made during installation.

        These can be, e.g., forbidden by the freeze process."""

        shutil.rmtree(join(self.openerp_dir, 'openerp.egg-info'))
        # setup rewritten without PIL is cleaned during the process itself

    def buildout_cfg_name(self, argv=None):
        """Return the name of the config file that's been called.
        """

        # not using optparse because it's not obvious how to tell it to
        # consider just one option and ignore the others.

        if argv is None:
            argv = sys.argv[1:]

        # -c FILE or --config FILE syntax
        for opt in ('-c', '--config'):
            try:
                i = argv.index(opt)
            except ValueError:
                continue
            else:
                return argv[i+1]

        # --config=FILE syntax
        prefix = "--config="
        for a in argv:
            if a.startswith(prefix):
                return a[len(prefix):]

        return 'buildout.cfg'
