# coding: utf-8
from os.path import join, basename
import os
import sys
import re
import tarfile
import setuptools
import logging
import stat
import imp
import shutil
try:
    from ConfigParser import ConfigParser, RawConfigParser  # Python 2
except ImportError:
    from configparser import ConfigParser, RawConfigParser  # Python 3
import distutils.core
import pkg_resources
try:
    from collections import OrderedDict
except ImportError:  # Python < 2.7
    from ordereddict import OrderedDict  # noqa
from zc.buildout.easy_install import MissingDistribution
from zc.buildout import UserError
from zc.buildout.easy_install import VersionConflict
from zc.buildout.easy_install import Installer

from zc.buildout.easy_install import IncompatibleConstraintError

import zc.recipe.egg
try:
    import httplib  # Python 2
except ImportError:
    from http import client as httplib  # Python 3
from email import utils as email_utils
try:
    from urllib import urlretrieve  # Python 2
except ImportError:
    from urllib.request import urlretrieve  # Python 3
try:
    from urlparse import urlparse  # Python 2
except ImportError:
    from urllib.parse import urlparse  # Python 3
from . import vcs
from . import utils
from .utils import option_splitlines, option_strip, conf_ensure_section

logger = logging.getLogger(__name__)

if sys.version_info >= (2, 7):
    unicode = str
else:
    from .utils import next


def rfc822_time(h):
    """Parse RFC 2822-formatted http header and return a time int."""
    email_utils.mktime_tz(email_utils.parsedate_tz(h))


def get_content_type(msg):
    """Return the mimetype of the HTTP message.
    This is a helper to support Python 2 and 3.
    """
    try:
        return msg.type
    except AttributeError:
        return msg.get_content_type()


class MainSoftware(object):
    """Placeholder to represent the main software instead of an addon location.

    Should just have a singleton instance: :data:`main_software`,
    whose meaning depends on the concrete recipe class using it.

    For example, in :class:`anybox.recipe.odoo.server.ServerRecipe`,
    :data:`main_software` represents the OpenObject server or the Odoo
    standard distribution.
    """

    def __str__(self):
        return 'Main Software'


main_software = MainSoftware()

GP_VCS_EXTEND_DEVELOP = 'vcs-extend-develop'
GP_DEVELOP_DIR = 'develop-dir'

WITH_ODOO_REQUIREMENTS_FILE_OPTION = 'apply-requirements-file'


def pip_version():
    import pip
    # we don't use pip or setuptools APIs for that to avoid going
    # in a swath of instability.
    # TODO we could try and use the version class from runtime.session
    # (has the advantage over pkf_resources' of direct transparent
    # comparison to tuples), but that'd introduced logical deps problems
    # that I don't want to solve right now.

    pip_version = pip.__version__
    # Naturally, pip has strictly conformed to PEP440, and does not use
    # version epochs, since at least v1.2. the oldest I could easily check
    # (we claim to support >= 1.4.1).
    # This equates all pre versions with the final one, and that's good
    # enough for current purposes:
    for suffix in ('a', 'b', 'rc', '.dev', '.post'):
        pip_version = pip_version.split(suffix)[0]
    return tuple(int(x) for x in pip_version.split('.'))


class BaseRecipe(object):
    """Base class for other recipes.

    It implements notably fetching of the main software part plus addons.

    The :attr:`sources` attribute is a ``dict`` storing how to fetch the main
    software part and the specified addons, with the following structure:

       ``local path -> (type, location_spec, options)``, in which:

       :local path: is either the :data:`main_software` singleton
                    (see :class:`MainSoftware`) or a local path to an
                    addons directory.
       :type: can be either

              * ``'local'``
              * ``'downloadable'``
              * one of the supported vcs

       :location_spec: is, depending on the type, a tuple specifying how
                       fetch is to be done:

                       ``url``, or ``(vcs_url, vcs_revision)``
                       or ``None``
       :addons options: are typically used to specify that the addons
                        directory is actually a subdir of the specified one.

                        VCS support classes (see
                        :mod:`anybox.recipe.odoo.vcs`) can implemented their
                        dedicated options

    The :attr:`merges` attribute is a ``dict`` storing how to fetch additional
    changes to merge into VCS type sources:

       ``local path -> [(type, location_spec, options), ... ]``

       See :attr:`sources` for the meaning of the various components. Note that
       in :attr:`merges`, values are a list of triples instead of only a single
       triple as values in :attr:`sources` because there can be multiple merges
       on the same local path.

    """

    release_dl_url = {
    }
    """Base URLs to look for official, released versions.

    There are currently no official releases for Odoo, but the recipe
    has been designed at the time of OpenERP 6.0 and some parts of its code
    at least expect this dict to exist. Besides, official releases may reappear
    at some point.
    """

    nightly_dl_url = {
        '10.0rc1c': 'http://nightly.odoo.com/10.0/nightly/src/',
    }
    """Base URLs to look for nightly versions.

    The URL for 8.0 may have to be adapted once it's released for good.
    This one is guessed from 7.0 and is needed by unit tests.
    """
    recipe_requirements = ()  # distribution required for the recipe itself
    recipe_requirements_paths = ()  # a default value is useful in unit tests
    requirements = ()  # requirements for what the recipe installs to run
    soft_requirements = ()  # subset of requirements that's not necessary
    addons_paths = ()

    # Caching logic for the main Odoo part (e.g, without addons)
    # Can be 'filename' or 'http-head'
    main_http_caching = 'filename'

    is_git_layout = False
    """True if this is the git layout, as seen from the move to GitHub.

    In this layout, the standard addons other than ``base`` are in a ``addons``
    directory right next to the ``odoo`` package.
    """

    with_odoo_requirements_file = False
    """Whether attempt to use the 'requirements.txt' shipping with Odoo"""

    def bool_opt_get(self, name, is_global=False):
        """Retrieve an option and interpret it as boolean.

        Factorized to improve code readability.

        :param is_global: if ``True``, the option is taken from the
                          global buildout options instead of the part
                          taken care of by this recipe instance.
        """
        options = self.b_options if is_global else self.options
        return options.get(name, '').lower() == 'true'

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

        if self.bool_opt_get(WITH_ODOO_REQUIREMENTS_FILE_OPTION):
            logger.debug("%s option: adding 'pip' to the recipe requirements",
                         WITH_ODOO_REQUIREMENTS_FILE_OPTION)
            self.with_odoo_requirements_file = True
            self.recipe_requirements = list(self.recipe_requirements)
            self.recipe_requirements.append('pip')

        # same as in zc.recipe.eggs
        self.extra_paths = [
            join(self.buildout_dir, p.strip())
            for p in option_splitlines(self.options.get('extra-paths'))
        ]
        self.options['extra-paths'] = os.linesep.join(self.extra_paths)

        self.downloads_dir = self.make_absolute(
            self.b_options.get('odoo-downloads-directory', 'downloads'))
        self.version_wanted = None  # from the buildout
        self.version_detected = None  # string from the odoo setup.py
        self.parts = self.buildout['buildout']['parts-directory']
        self.odoo_dir = None
        self.archive_filename = None
        self.archive_path = None  # downloaded tar.gz

        if options.get('scripts') is None:
            options['scripts'] = ''

        # a dictionnary of messages to display in case a distribution is
        # not installable (kept PIL to have an example, but Odoo is on Pillow)
        self.missing_deps_instructions = {
            'PIL': ("You don't need to require it for Odoo any more, since "
                    "the recipe automatically adds a dependency to Pillow. "
                    "If you really need it for other reasons, installing it "
                    "system-wide is a good option. "),
        }

        self.odoo_installed = []

        self.etc = self.make_absolute(options.get('etc-directory', 'etc'))
        self.bin_dir = self.buildout['buildout']['bin-directory']
        self.config_path = join(self.etc, self.name + '.cfg')
        for d in self.downloads_dir, self.etc:
            if not os.path.exists(d):
                logger.info('Created %s/ directory' % basename(d))
                os.mkdir(d)

        self.sources = OrderedDict()
        self.merges = OrderedDict()
        self.parse_addons(options)
        self.parse_version()
        self.parse_revisions(options)
        self.parse_merges(options)

    def parse_version(self):
        """Set the main software in :attr:`sources` and related attributes.
        """
        self.version_wanted = option_strip(self.options.get('version'))
        if self.version_wanted is None:
            raise UserError('You must specify the version')

        self.preinstall_version_check()

        version_split = self.version_wanted.split()

        if len(version_split) == 1:
            # version can be a simple version name, such as 6.1-1
            if len(self.version_wanted.split('.')[0]) == 2:
                major_wanted = self.version_wanted[:4]
            elif len(self.version_wanted.split('.')[0]) == 1:
                major_wanted = self.version_wanted[:3]
            pattern = self.release_filenames[major_wanted]
            if pattern is None:
                raise UserError('Odoo version %r'
                                'is not supported' % self.version_wanted)

            self.archive_filename = pattern % self.version_wanted
            self.archive_path = join(self.downloads_dir, self.archive_filename)
            base_url = self.options.get(
                'base_url', self.release_dl_url[major_wanted])
            self.sources[main_software] = (
                'downloadable',
                '/'.join((base_url.strip('/'), self.archive_filename)), None)
            return

        # in all other cases, the first token is the type of version
        type_spec = version_split[0]
        if type_spec in ('local', 'path'):
            self.odoo_dir = join(self.buildout_dir, version_split[1])
            self.sources[main_software] = ('local', None)
        elif type_spec == 'url':
            url = version_split[1]
            self.archive_filename = urlparse(url).path.split('/')[-1]
            self.archive_path = join(self.downloads_dir, self.archive_filename)
            self.sources[main_software] = ('downloadable', url, None)
        elif type_spec == 'nightly':
            if len(version_split) != 3:
                raise UserError(
                    "Unrecognized nightly version specification: "
                    "%r (expecting series, number) % version_split[1:]")
            self.nightly_series, self.version_wanted = version_split[1:]
            type_spec = 'downloadable'
            if self.version_wanted == 'latest':
                self.main_http_caching = 'http-head'
            series = self.nightly_series
            self.archive_filename = (
                self.nightly_filenames[series] % self.version_wanted)
            self.archive_path = join(self.downloads_dir, self.archive_filename)
            base_url = self.options.get('base_url',
                                        self.nightly_dl_url[series])
            self.sources[main_software] = (
                'downloadable',
                '/'.join((base_url.strip('/'), self.archive_filename)),
                None)
        else:
            # VCS types
            type_spec, url, repo_dir, self.version_wanted = version_split[0:4]
            options = dict(opt.split('=') for opt in version_split[4:])
            self.odoo_dir = join(self.parts, repo_dir)
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
        # Some earlier processing leaves tmp dirs behind, that may
        # mask what we just installed (especially harmful in case of pip)
        sys.path[0:0] = self.recipe_requirements_paths

    def merge_requirements(self, reqs=None):
        """Merge eggs option with self.requirements.


        TODO refactor all this: merge requirements is not idempotent, it
        appends. Overall, this going back and forth between the serialized
        form (self.options['eggs']) and the parsed version has growed too
        much, up to the point where it's not natural at all.
        """
        if reqs is None:
            reqs = self.requirements
        serial = '\n'.join(reqs)

        if 'eggs' not in self.options:
            self.options['eggs'] = serial
        else:
            self.options['eggs'] += '\n' + serial

    def list_develops(self):
        """At any point in time, list the projects that have been developed.

        This can work as soon as the recipe is instantiated
        (because the 'buildout' part) has already been executed.
        In particular, it does not rely on the workingset init done by
        :class:`zc.buildout.easy_install.Installer` and
        can be used in precedence rules that need to be executed before calling
        the Installer indirectly via ``zc.recipe.eggs``

        :return: list of project names

        Implementation simply lists the develop eggs directory
        There's probably better to be done.
        """
        devdir_contents = (f.rsplit('.', 1) for f in os.listdir(
            self.b_options['develop-eggs-directory']))
        return [s[0] for s in devdir_contents if s[1] == 'egg-link']

    def apply_odoo_requirements_file(self):
        """Try and read Odoo's 'requirements.txt' and apply it.

        This file appeared in the course of Odoo 8 lifetime. If not available,
        a warning is issued, that's all.

        Entries from the requirements file are applied if there is not already
        an entry in the versions section for the same project.

        A more interesting behaviour would be to apply then if they don't
        contradict an existing entry in the versions section, but that's far
        more complicated.
        """
        req_fname = 'requirements.txt'
        req_path = join(self.odoo_dir, req_fname)
        if not os.path.exists(req_path):
            logger.warn("%r not found in this version of "
                        "Odoo, although the configuration said to use it. "
                        "Proceeding anyway.", req_fname)
            return

        # pip wouldn't be importable before the call to
        # install_recipe_requirements()

        # if an extension has used pip before, it can be left in a
        # strange state where pip.req is not usable nor reloadable
        # anymore. (may have something to do with the fact that the
        # first import is done from a tmp dir
        # that does not exist any more).
        # So, better to clean that before hand.
        for k in list(sys.modules.keys()):
            if k.split('.', 1)[0] == 'pip':
                del sys.modules[k]

        # it is useless to mutate the versions section at this point
        # it's already been used to populate the Installer class variable
        versions = Installer._versions
        develops = self.list_develops()

        new_reqs = set()
        if pip_version() < (8, 1, 1):
            self.read_requirements_pip_before_v8(req_path, versions, develops)
        else:
            self.read_requirements_pip_after_v8(req_path, versions, develops)
        self.merge_requirements(reqs=new_reqs)

    def read_requirements_pip_before_v8(self, req_path, versions, develops):
        from pip.req import parse_requirements
        if pip_version() < (1, 5):
            parsed = parse_requirements(req_path)
        else:
            # pip internals are protected against the fact of not passing
            # a session with ``is None``. OTOH, the session is not used
            # if the file is local (direct path, not an URL), so we cheat
            # it.
            # Although this hack still works with pip 8, it's considered to be
            # the kind of thing that can depend on pip version
            fake_session = object()
            parsed = parse_requirements(req_path, session=fake_session)

        for inst_req in parsed:
            req = inst_req.req
            logger.debug("Considering requirement from Odoo's file %s",
                         req)
            # GR something more interesting would be to apply the
            # requirement if it does not contradict an existing one.
            # For now that's too much complicated, but check later if
            # zc.buildout.easy_install._constrain() fits the bill.

            project_name = req.project_name
            if project_name not in self.requirements:
                # TODO maybe convert self.requirements to a set (in
                # next unstable branch)
                self.requirements.append(project_name)

            if project_name in versions:
                logger.debug("Requirement from Odoo's file %s superseded "
                             "by buildout versions configuration as %r",
                             req, versions[project_name])
                continue

            if project_name in develops:
                logger.debug("Requirement from Odoo's file %s superseded "
                             "by a direct develop directive", req)
                continue

            if not req.specs:
                continue

            supported = True

            if len(req.specs) > 1:
                supported = False
            spec = req.specs[0]
            if spec[0] != '==':
                supported = False

            if not supported:
                raise UserError(
                    "Version requirement %s from Odoo's requirement file "
                    "is too complicated to be taken automatically into "
                    "account. Please translate it in your [%s] "
                    "configuration section and, "
                    "if from a public fork of Odoo, report this as a "
                    "request for improvement on the buildout recipe." % (
                        req, self.b_options.get('versions', 'versions')))

            logger.debug("Applying requirement %s from Odoo's file",
                         req)
            versions[project_name] = spec[1]

    def read_requirements_pip_after_v8(self, req_path, versions, develops):
        from pip.req import parse_requirements
        # pip internals are protected against the fact of not passing
        # a session with ``is None``. OTOH, the session is not used
        # if the file is local (direct path, not an URL), so we cheat
        # it.
        fake_session = object()
        for inst_req in parse_requirements(req_path, session=fake_session):
            req = inst_req.req
            logger.debug("Considering requirement from Odoo's file %s",
                         req)
            # GR something more interesting would be to apply the
            # requirement if it does not contradict an existing one.
            # For now that's too much complicated, but check later if
            # zc.buildout.easy_install._constrain() fits the bill.

            # zc.buildout does its version comparison in lower case
            # watch out for develops if that's the same !
            project_name = req.name.lower()
            if project_name not in self.requirements:
                # TODO maybe convert self.requirements to a set (in
                # next unstable branch)
                self.requirements.append(project_name)

            if project_name in versions:
                logger.debug("Requirement from Odoo's file %s superseded "
                             "by buildout versions configuration as %r",
                             req, versions[project_name])
                continue

            if project_name in develops:
                logger.debug("Requirement from Odoo's file %s superseded "
                             "by a direct develop directive", req)
                continue

            specs = req.specifier
            if not specs:
                continue

            supported = True

            if len(specs) > 1:
                supported = False
            spec = next(specs.__iter__())
            if spec.operator != '==':
                supported = False

            if not supported:
                raise UserError(
                    "Version requirement %s from Odoo's requirement file "
                    "is too complicated to be taken automatically into "
                    "account. Please translate it in your [%s] "
                    "configuration section and, "
                    "if from a public fork of Odoo, report this as a "
                    "request for improvement on the buildout recipe." % (
                        req, self.b_options.get('versions', 'versions')))

            logger.debug("Applying requirement %s from Odoo's file",
                         req)
            versions[project_name] = spec.version

    def install_requirements(self):
        """Install egg requirements and scripts.

        If some distributions are known as soft requirements, will retry
        without them
        """
        if self.with_odoo_requirements_file:
            self.apply_odoo_requirements_file()

        while True:
            missing = None
            eggs_recipe = zc.recipe.egg.Scripts(self.buildout, '',
                                                self.options)
            try:
                eggs_recipe.install()
            except MissingDistribution as exc:
                missing = exc.data[0].project_name
            except VersionConflict as exc:
                # GR not 100% sure, but this should mean a conflict with an
                # already loaded version (don't know what can lead to this
                # 'already', have seen it with zc.buildout itself only so far)
                # In any case, removing the requirement can't make for a sane
                # recovery
                raise
            except IncompatibleConstraintError as exc:
                missing = exc.args[2].project_name
            except UserError as exc:  # happens only for zc.buildout >= 2.0
                missing = unicode(exc).split(os.linesep)[0].split()[-1]
                missing = re.split(r'[=<>]', missing)[0]
            else:
                break

            logger.error("Could not find or install %r. " +
                         self.missing_deps_instructions.get(missing, '') +
                         " Original exception %s.%s says: %s",
                         missing,
                         exc.__class__.__module__, exc.__class__.__name__, exc)
            if missing not in self.soft_requirements:
                raise exc

            eggs = set(self.options['eggs'].split(os.linesep))
            if missing not in eggs:
                logger.error("Soft requirement %r is also an indirect "
                             "dependency (either of OpenERP/Odoo or of "
                             "one listed in config file). Can't retry.",
                             missing)
                raise exc

            logger.warn("%r is a direct soft requirement, "
                        "retrying without it", missing)
            eggs.discard(missing)
            self.options['eggs'] = os.linesep.join(eggs)

        self.eggs_reqs, self.eggs_ws = eggs_recipe.working_set()
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

        Used as a fallback in case reading setup.py failed, which happened
        in an old OpenERP version. Could become the norm, but setup is also
        used to list dependencies.
        """
        with open(join(self.odoo_dir, 'bin', 'release.py'), 'rb') as f:
            mod = imp.load_module('release', f, 'release.py',
                                  ('.py', 'r', imp.PY_SOURCE))
        self.version_detected = mod.version

    def read_odoo_setup(self):
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
        with open(join(self.odoo_dir, 'setup.py'), 'rb') as f:
            saved_argv = sys.argv
            sys.argv = ['setup.py', 'develop']
            try:
                imp.load_module('setup', f, 'setup.py',
                                ('.py', 'r', imp.PY_SOURCE))
            except SystemExit as exception:
                if 'dsextras' in unicode(exception):
                    raise EnvironmentError(
                        'Please first install PyGObject and PyGTK !')
                else:
                    try:
                        self.read_release()
                    except Exception as exc:
                        raise EnvironmentError(
                            'Problem while reading Odoo release.py: %s' % exc)
            except ImportError as exception:
                if 'babel' in unicode(exception):
                    raise EnvironmentError(
                        'OpenERP setup.py has an unwanted import Babel.\n'
                        '=> First install Babel on your system or '
                        'virtualenv :(\n'
                        '(sudo aptitude install python-babel, '
                        'or pip install babel)')
                else:
                    raise exception
            except Exception as exception:
                raise EnvironmentError('Problem while reading Odoo '
                                       'setup.py: %s' % exception)
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
        the recipe consumes a first member in the tar file to get the odoo
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

    def develop(self, src_directory):
        """Develop the specified source distribution.

        Any call to ``zc.recipe.eggs`` will use that developped version.
        :meth:`develop` launches a subprocess, to which we need to forward
        the paths to requirements via PYTHONPATH.

        :param setup_has_pil: if ``True``, an altered version of setup that
                              does not require PIL is produced to perform the
                              develop, so that installation can be done with
                              ``Pillow`` instead. Recent enough versions of
                              OpenERP/Odoo are directly based on Pillow.
        :returns: project name of the distribution that's been "developed"
                  This is useful for OpenERP/Odoo itself, whose project name
                  changed within the 8.0 stable branch.
        """
        logger.debug("Developing %r", src_directory)
        develop_dir = self.b_options['develop-eggs-directory']
        pythonpath_bak = os.getenv('PYTHONPATH')
        os.putenv('PYTHONPATH', ':'.join(self.recipe_requirements_paths))

        egg_link = zc.buildout.easy_install.develop(src_directory, develop_dir)

        suffix = '.egg-link'

        if pythonpath_bak is None:
            os.unsetenv('PYTHONPATH')
        else:
            os.putenv('PYTHONPATH', pythonpath_bak)

        if not egg_link.endswith(suffix):
            raise RuntimeError(
                "Development of OpenERP/Odoo distribution "
                "produced an unexpected egg link: %r" % egg_link)

        return os.path.basename(egg_link)[:-len(suffix)]

    def parse_addons(self, options):
        """Parse the addons options into :attr:`sources`.

        See :class:`BaseRecipe` for the structure of :attr:`sources`.
        """

        for line in option_splitlines(options.get('addons')):
            split = line.split()
            if not split:
                return
            try:
                loc_type = split[0]
                spec_len = 2 if loc_type == 'local' else 4

                options = dict(opt.split('=') for opt in split[spec_len:])
                if loc_type == 'local':
                    addons_dir = split[1]
                    location_spec = None
                else:  # vcs
                    repo_url, addons_dir, repo_rev = split[1:4]
                    location_spec = (repo_url, repo_rev)
            except:
                raise UserError("Could not parse addons line: %r. "
                                "Please check format " % line)

            addons_dir = addons_dir.rstrip('/')  # trailing / can be harmful
            group = options.get('group')
            if group:
                split = os.path.split(addons_dir)
                addons_dir = os.path.join(split[0], group, split[1])
            self.sources[addons_dir] = (loc_type, location_spec, options)

    def parse_merges(self, options):
        """Parse the merge options into :attr:`merges`.

        See :class:`BaseRecipe` for the structure of :attr:`merges`.
        """

        for line in option_splitlines(options.get('merges')):
            split = line.split()
            if not split:
                return
            loc_type = split[0]
            if loc_type not in ('bzr', 'git'):
                raise UserError("Only merges of type 'bzr' and 'git' are "
                                "currently supported.")
            options = dict(opt.split('=') for opt in split[4:])
            if loc_type == 'bzr':
                options['bzr-init'] = 'merge'
            else:
                options['merge'] = True

            repo_url, local_dir, repo_rev = split[1:4]
            location_spec = (repo_url, repo_rev)

            local_dir = local_dir.rstrip('/')  # trailing / can be harmful
            self.merges.setdefault(local_dir, []).append(
                (loc_type, location_spec, options))

    def parse_revisions(self, options):
        """Parse revisions options and update :attr:`sources`.

        It is assumed that :attr:`sources` has already been populated, and
        notably has a :data:`main_software` entry.
        This allows for easy fixing of revisions in an extension buildout

        See :class:`BaseRecipe` for the structure of :attr:`sources`.
        """
        for line in option_splitlines(options.get('revisions')):
            split = line.split()
            if len(split) > 2:
                raise UserError("Invalid revisions line: %r" % line)

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
                raise UserError("In revision line %r : can't fix a revision "
                                "for non-vcs source" % line)

            logger.info("%s will be on revision %r", local_path, revision)
            self.sources[local_path] = (
                (source[0], (source[1][0], revision)) + source[2:]
            )

    def retrieve_addons(self):
        """Peform all lookup and downloads specified in :attr:`sources`.

        See :class:`BaseRecipe` for the structure of :attr:`sources`.
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
            if loc_type == 'git':
                options['depth'] = self.options.get('git-depth')
            options.update(addons_options)

            group = addons_options.get('group')
            group_dir = None
            if group:
                if loc_type == 'local':
                    raise UserError(
                        "Automatic grouping of addons is not supported for "
                        "local addons such as %r, because the recipe "
                        "considers that write operations in a local "
                        "directory is "
                        "outside of its reponsibilities (in other words, "
                        "it's better if "
                        "you create yourself the intermediate directory." % (
                            local_dir, ))

                group_dir = os.path.dirname(local_dir)
                if not os.path.exists(group_dir):
                    os.makedirs(group_dir)
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
            if group_dir:
                addons_dir = group_dir
            else:
                addons_dir = local_dir

            if subdir:
                addons_dir = join(addons_dir, subdir)

            manifest = os.path.join(addons_dir, '__manifest__.py')
            manifest_pre_v10 = os.path.join(addons_dir, '__openerp__.py')
            if os.path.isfile(manifest) or os.path.isfile(manifest_pre_v10):
                raise UserError("Standalone addons such as %r "
                                "are now supported by means "
                                "of the explicit 'group' option. Please "
                                "update your buildout configuration. " % (
                                    addons_dir))

            if addons_dir not in self.addons_paths:
                self.addons_paths.append(addons_dir)

    def revert_sources(self):
        """Revert all sources to the revisions specified in :attr:`sources`.
        """
        for target, desc in self.sources.items():
            if desc[0] in ('local', 'downloadable'):
                continue

            vcs_type, vcs_spec, options = desc
            local_dir = self.odoo_dir if target is main_software else target
            local_dir = self.make_absolute(local_dir)
            repo = vcs.repo(vcs_type, local_dir, vcs_spec[0], **options)
            try:
                repo.revert(vcs_spec[1])
            except NotImplementedError:
                logger.warn("vcs-revert: not implemented for %s "
                            "repository at %s", vcs_type, local_dir)
            else:
                logger.info("Reverted %s repository at %s",
                            vcs_type, local_dir)

    def retrieve_merges(self):
        """Peform all VCS merges specified in :attr:`merges`.
        """
        if self.options.get('vcs-revert', '').strip().lower() == 'on-merge':
            logger.info("Reverting all sources before merge")
            self.revert_sources()
        for local_dir, source_specs in self.merges.items():
            for source_spec in source_specs:
                loc_type, loc_spec, merge_options = source_spec
                local_dir = self.make_absolute(local_dir)
                options = dict(offline=self.offline,
                               clear_locks=self.vcs_clear_locks)
                options.update(merge_options)

                for k, v in self.options.items():
                    if k.startswith(loc_type + '-'):
                        options[k] = v

                repo_url, repo_rev = loc_spec
                vcs.get_update(loc_type, local_dir, repo_url, repo_rev,
                               clear_retry=self.clear_retry,
                               **options)

    def main_download(self):
        """HTTP download for main part of the software to self.archive_path.
        """
        if self.offline:
            raise IOError("%s not found, and offline "
                          "mode requested" % self.archive_path)
        url = self.sources[main_software][1]
        logger.info("Downloading %s ..." % url)

        try:
            msg = urlretrieve(url, self.archive_path)
            if get_content_type(msg[1]) == 'text/html':
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

        url = self.sources[main_software][1]
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
        """Lookup or fetch the main software.

        See :class:`MainSoftware` and :class:`BaseRecipe` for explanations.
        """

        source = self.sources[main_software]
        type_spec = source[0]
        logger.info('Selected install type: %s', type_spec)
        if type_spec == 'local':
            logger.info('Local directory chosen, nothing to do')
            if self.clean:
                utils.clean_object_files(self.odoo_dir)
        elif type_spec == 'downloadable':
            # download if needed
            if ((self.archive_path and
                 not os.path.exists(self.archive_path)) or
                (self.main_http_caching == 'http-head' and
                 self.is_stale_http_head())):
                self.main_download()

            logger.info(u'Inspecting %s ...' % self.archive_path)
            tar = tarfile.open(self.archive_path)
            first = tar.members[0]
            # Everything that follows assumes all tarball members
            # are inside a directory with an expected name such
            # as odoo-6.1-1
            assert(first.isdir())
            extracted_name = first.name.split('/')[0]
            self.odoo_dir = join(self.parts, extracted_name)
            # protection against malicious tarballs
            assert(not os.path.isabs(extracted_name))
            assert(self.odoo_dir.startswith(self.parts))

            logger.info("Cleaning existing %s", self.odoo_dir)
            if os.path.exists(self.odoo_dir):
                shutil.rmtree(self.odoo_dir)
            logger.info(u'Extracting %s ...' % self.archive_path)
            self.sandboxed_tar_extract(extracted_name, tar, first=first)
            tar.close()
        else:
            url, rev = source[1]
            options = dict((k, v) for k, v in self.options.items()
                           if k.startswith(type_spec + '-'))
            if type_spec == 'git':
                options['depth'] = options.pop('git-depth', None)

            options.update(source[2])
            if self.clean:
                options['clean'] = True
            vcs.get_update(type_spec, self.odoo_dir, url, rev,
                           offline=self.offline,
                           clear_retry=self.clear_retry, **options)

    def _register_extra_paths(self):
        """Add odoo paths into the extra-paths (used in scripts' sys.path).

        This is useful up to the 6.0 series only, because in later version,
        the 'odoo' directory is a proper distribution that we develop, with
        the effect of putting it on the path automatically.
        """
        extra = self.extra_paths
        self.options['extra-paths'] = os.linesep.join(extra)

    def install(self):
        os.chdir(self.parts)

        freeze_to = self.options.get('freeze-to')
        extract_downloads_to = self.options.get('extract-downloads-to')

        if ((freeze_to is not None or extract_downloads_to is not None) and
                not self.offline):
            raise UserError("To freeze a part, you must run offline "
                            "so that there's no modification from what "
                            "you just tested. Please rerun with -o.")

        if extract_downloads_to is not None and freeze_to is None:
            freeze_to = os.path.join(extract_downloads_to,
                                     'extracted_from.cfg')

        self.retrieve_main_software()
        self.retrieve_addons()
        self.retrieve_merges()

        self.install_recipe_requirements()
        os.chdir(self.odoo_dir)  # GR probably not needed any more
        self.read_odoo_setup()

        if (self.sources[main_software][0] == 'downloadable' and
                self.version_wanted == 'latest'):
            self.nightly_version = self.version_detected.split('-', 1)[1]
            logger.warn("Detected 'nightly latest version', you may want to "
                        "fix it in your config file for replayability: \n    "
                        "version = " + self.dump_nightly_latest_version())

        self.finalize_addons_paths()
        self._register_extra_paths()

        if self.version_detected is None:
            raise EnvironmentError('Version of Odoo could not be detected')
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
        config = RawConfigParser()
        config.read(self.config_path)
        for recipe_option in self.options:
            if '.' not in recipe_option:
                continue
            section, option = recipe_option.split('.', 1)
            conf_ensure_section(config, section)
            config.set(section, option, self.options[recipe_option])
        with open(self.config_path, 'w') as configfile:
            config.write(configfile)

        if extract_downloads_to:
            self.extract_downloads_to(extract_downloads_to)
        if freeze_to:
            self.freeze_to(freeze_to)
        return self.odoo_installed

    def dump_nightly_latest_version(self):
        """After download/analysis of 'nightly latest', give equivalent spec.
        """
        return ' '.join(('nightly', self.nightly_series, self.nightly_version))

    def freeze_to(self, out_config_path):
        """Create an extension buildout freezing current revisions & versions.
        """

        logger.info("Freezing part %r to config file %r", self.name,
                    out_config_path)
        out_conf = ConfigParser()

        frozen = getattr(self.buildout, '_odoo_recipe_frozen', None)
        if frozen is None:
            frozen = self.buildout._odoo_recipe_frozen = set()

        if out_config_path in frozen:
            # read configuration started by other recipe
            out_conf.read(self.make_absolute(out_config_path))
        else:
            self._prepare_frozen_buildout(out_conf)

        # The name the versions section is hardcoded, but that's tolerable
        # because that's actually the one we *produce*
        self._freeze_egg_versions(out_conf, 'versions')

        conf_ensure_section(out_conf, self.name)
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
                    abspath = self.odoo_dir
                    self.cleanup_odoo_dir()
            else:
                abspath = self.make_absolute(local_path)

            if source_type == 'downloadable':
                continue

            required_rev = source[1][1]
            revision = self._freeze_vcs_source(
                source_type, abspath, required_rev)

            # here it would be tempting not to repeat the freeze if
            # the resulting revision is equal to revision_rev, BUT
            # if revision_rev itself comes from use of the 'revisons' option
            # then we could have masking of that in the extended buildout
            # this could be taken care of for aesthetics by careful use of
            # += and actually specification of what it should do for
            # the 'revisions' option. In the meanwhile, let's just play safe

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
        """Return a tuple of (raw, parsed, sub_dir, abs_path)
        vcs-extends-develop specifications.
        """
        sub_dir = self.b_options.get(
            GP_DEVELOP_DIR, '')
        base_path = self.make_absolute(sub_dir)
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

        if 'parse_editable' in dir(pip.req):  # pip < 6.0
            def parse_egg_dir(req_str):
                return pip.req.parse_editable(req_str)[0]
        else:
            def parse_egg_dir(req_str):
                ireq = pip.req.InstallRequirement.from_editable(req_str)
                # GR I'm worried because now this is also used as project
                # name in requirement, whereas it used to just be the target
                # directory
                editable_options = getattr(ireq, 'editable_options', None)
                if editable_options is not None:  # pip < 8.1.0
                    return editable_options['egg']
                try:
                    return ireq.req.name  # pip >= 8.1.2
                except AttributeError:
                    return ireq.req.project_name  # pip >=8.1.0, < 8.1.2

        ret = []
        for raw in option_splitlines(lines):
            target = parse_egg_dir(raw)
            abs_path = os.path.join(base_path, target)
            ret.append((raw, target, sub_dir, abs_path))
        return tuple(ret)

    def _prepare_frozen_buildout(self, conf):
        """Create the 'buildout' section in conf."""
        conf.add_section('buildout')
        conf.set('buildout', 'extends', self.buildout_cfg_name())
        conf.add_section('versions')
        conf.set('buildout', 'versions', 'versions')

        # freezing for gp.vcsdevelop
        extends = []
        for raw, _, _, abs_path in self._get_gp_vcs_develops():
            hash_split = raw.rsplit('#')
            url = hash_split[0]
            rev_split = url.rsplit('@', 1)
            url = rev_split[0]
            revspec = rev_split[1] if len(rev_split) == 2 else None
            vcs_type = url.split('+', 1)[0]
            # vcs-develop process adds .egg-info file (often forgotten in VCS
            # ignore files) and changes setup.cfg.
            # For now we'll have to allow local modifications.
            revision = self._freeze_vcs_source(vcs_type,
                                               abs_path,
                                               revspec,
                                               pip_compatible=True,
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

        This also forces not to use the requirements file from Odoo, hence
        avoiding a deploy-time dependency on pip for something that is not
        needed and could only be a source of issues.
        """
        conf_ensure_section(conf, self.name)
        conf.set(self.name, WITH_ODOO_REQUIREMENTS_FILE_OPTION, 'False')

        versions = dict((name, conf.get(section, name))
                        for name in conf.options(section))
        versions.update((name, egg.version)
                        for name, egg in self.ws.by_key.items()
                        if name not in exclude and
                        egg.precedence != pkg_resources.DEVELOP_DIST
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

    def _freeze_vcs_source(self, vcs_type, abspath, revspec,
                           pip_compatible=False,
                           allow_local_modification=False):

        """Return the frozen revision for the state of that VCS source.

        :param vcs_type: self-explanatory
        :param abspath: absolute path to local repository
        :param revspec: the revision specification as required in the buildout
                        configuration (can be suitable in itself and better
                        than what we can produce)
        :param pip_compatible: if ``True``, a pip compatible revision number
                               is issued. This depends on the precise vcs.
        :returns: ``None`` if ``revspec`` is already a frozen and reproducible
                  specification.
        """

        repo = vcs.repo(vcs_type, abspath, '')  # no need of remote URL

        if not allow_local_modification and repo.uncommitted_changes():
            self.local_modifications.append(abspath)

        if revspec is not None and repo.is_local_fixed_revision(revspec):
            return revspec
        parents = repo.parents(pip_compatible=pip_compatible)
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
        out_conf = ConfigParser()

        all_extracted = getattr(self.buildout, '_odoo_recipe_extracted',
                                None)
        if all_extracted is None:
            all_extracted = self.buildout._odoo_recipe_extracted = {}
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
        conf_ensure_section(out_conf, self.name)

        # remove bzr extra if needed
        recipe = self.options['recipe']
        pkg_extras, recipe_cls = recipe.split(':')
        extra_match = re.match(r'(.*?)\[(.*?)\]', pkg_extras)
        if extra_match is not None:
            recipe_pkg = extra_match.group(1)
            extras = set(e.strip() for e in extra_match.group(2).split(','))
            extras.discard('bzr')
            extracted_recipe = recipe_pkg
            if extras:
                extracted_recipe += '[%s]' % ','.join(extras)
            extracted_recipe += ':' + recipe_cls
            out_conf.set(self.name, 'recipe', extracted_recipe)
        else:
            out_conf.set(self.name, 'recipe', recipe)

        addons_option = []
        for local_path, source in self.sources.items():
            source_type = source[0]
            if local_path is main_software:
                rel_path = self._extract_main_software(source_type, target_dir,
                                                       extracted)
                out_conf.set(self.name, 'version', 'local ' + rel_path)
                continue

            # stripping the group option that won't be usefult
            # and actually harming for extracted buildout conf
            options = source[2]
            group = options.pop('group', None)
            if group:
                target_local_path = os.path.dirname(local_path)
                if group != os.path.basename(target_local_path):
                    raise RuntimeError(
                        "Inconsistent configuration that "
                        "should not happen: group=%r, but resulting path %r "
                        "does not have it as its parent" % (group, local_path))
            else:
                target_local_path = local_path

            addons_line = ['local', target_local_path]
            addons_line.extend('%s=%s' % (opt, val)
                               for opt, val in options.items())
            addons_option.append(' '.join(addons_line))

            abspath = self.make_absolute(local_path)
            if source_type == 'downloadable':
                shutil.copytree(abspath,
                                os.path.join(target_dir, local_path))
            elif source_type != 'local':  # vcs
                self._extract_vcs_source(source_type, abspath, target_dir,
                                         local_path, extracted)
        # remove duplicates preserving order
        addons_option = list(OrderedDict.fromkeys(addons_option))
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
        target_path = os.path.join(target_dir, local_path)

        if not os.path.exists(target_path):
            os.makedirs(target_path)
        if target_path in extracted:
            return

        repo = vcs.repo(vcs_type, repo_path, '')  # no need of remote URL
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
        if not self.odoo_dir.startswith(self.buildout_dir):
            raise RuntimeError(
                "Main odoo directory %r outside of buildout "
                "directory, don't know how to handle that" % self.odoo_dir)

        local_path = self.odoo_dir[len(self.buildout_dir + os.sep):]
        target_path = join(target_dir, local_path)
        if target_path in extracted:
            return local_path

        if source_type == 'downloadable':
            shutil.copytree(self.odoo_dir, target_path)
        elif source_type != 'local':  # see docstring for 'local'
            self._extract_vcs_source(source_type, self.odoo_dir, target_dir,
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

        develops = set(option_splitlines(self.b_options.get('develop')))

        extracted = set()
        for raw, target, sub_dir, abs_path in self._get_gp_vcs_develops():
            target_sub_dir = os.path.join(sub_dir, target)
            vcs_type = raw.split('+', 1)[0]
            self._extract_vcs_source(vcs_type, abs_path,
                                     target_dir, target_sub_dir, extracted)
            # looks silly, but better for uniformity:
            develops.add(target_sub_dir)

        bdir = os.path.join(self.buildout_dir, '')
        conf.set('buildout', 'develop',
                 os.linesep.join(d[len(bdir):] if d.startswith(bdir) else d
                                 for d in develops))

        # remove gp.vcsdevelop from extensions
        exts = self.buildout['buildout'].get('extensions', '').split()
        if 'gp.vcsdevelop' in exts:
            exts.remove('gp.vcsdevelop')
        conf.set('buildout', 'extensions', '\n'.join(exts))

    def _install_script(self, name, content):
        """Install and register a scripbont with prescribed name and content.

        Return the script path
        """
        path = join(self.bin_dir, name)
        f = open(path, 'w')
        f.write(content)
        f.close()
        os.chmod(path, stat.S_IRWXU)
        self.odoo_installed.append(path)
        return path

    def _install_startup_scripts(self):
        raise NotImplementedError

    def _create_default_config(self):
        raise NotImplementedError

    update = install

    def _default_addons_path(self):
        """Set the default addons path for OpenERP > 6.0 pure python install

        Actual implementation is up to subclasses
        """

    def finalize_addons_paths(self, check_existence=True):
        """Add implicit paths and serialize in the addons_path option.

        :param check_existence: if ``True``, all the paths will be checked for
                                existence (useful for unit tests)
        """
        opt_key = 'options.addons_path'
        if opt_key in self.options:
            raise UserError("In part %r, direct use of %s is prohibited. "
                            "please use addons lines with type 'local' "
                            "instead." % (self.name, opt_key))

        base_addons = join(self.odoo_dir, 'odoo', 'addons')
        if os.path.exists(base_addons):
            self.addons_paths.insert(0, base_addons)

        self.insert_odoo_git_addons(base_addons)

        if check_existence:
            for path in self.addons_paths:
                assert os.path.isdir(path), (
                    "Not a directory: %r (aborting)" % path)

        self.options['options.addons_path'] = ','.join(self.addons_paths)

    def insert_odoo_git_addons(self, base_addons):
        """Insert the standard, non-base addons bundled within Odoo git repo.

        See `lp:1327756
        <https://bugs.launchpad.net/anybox.recipe.openerp/+bug/1327756>`_

        These addons are also part of the Github branch for prior versions,
        therefore we cannot rely on version knowledge; we check for existence
        instead.
        If not found (e.g, we are on a nightly for OpenERP <= 7), this method
        does nothing.

        The ordering of the different paths of addons is important.
        When several addons at different paths have the same name, the first
        of them being found is used. This can be used, for instance, to
        replace an official addon by another one by placing a different
        addons' path before the official one.

        If the official addons' path is already set in the config file
        (e.g. at the end), it will leave it at the end of the paths list,
        if it is not set, it will be placed at the beginning just after
        ``base`` addons' path.

        Care is taken not to break configurations that corrected this manually
        with a ``local`` source in the ``addons`` option.

        :param base_addons: the path to previously detected ``base`` addons,
                            to properly insert right after them
        """
        odoo_git_addons = join(self.odoo_dir, 'addons')
        if not os.path.isdir(odoo_git_addons):
            return

        self.is_git_layout = True
        addons_paths = self.addons_paths

        try:
            insert_at = addons_paths.index(base_addons) + 1
        except ValueError:
            insert_at = 0
        try:
            addons_paths.index(odoo_git_addons)
        except ValueError:
            addons_paths.insert(insert_at, odoo_git_addons)

    def cleanup_odoo_dir(self):
        """Revert local modifications that have been made during installation.

        These can be, e.g., forbidden by the freeze process."""

        # from here we can't guess whether it's 'odoo' or 'odoo'.
        # Nothing guarantees that this method is called after develop().
        # It is in practice now, but one day, the extraction as a separate
        # script of freeze/extract will become a reality.
        for proj_name in ('openerp', 'odoo'):
            egg_info_dir = join(self.odoo_dir, proj_name + '.egg-info')
            if os.path.exists(egg_info_dir):
                shutil.rmtree(egg_info_dir)

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
                return argv[i + 1]

        # --config=FILE syntax
        prefix = "--config="
        for a in argv:
            if a.startswith(prefix):
                return a[len(prefix):]

        return 'buildout.cfg'
