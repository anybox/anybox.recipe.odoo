"""Utilities to start a server process."""
import warnings
import sys
import os
import logging
from distutils.version import Version

try:
    import openerp
except ImportError:
    warnings.warn("This must be imported with a buildout openerp recipe "
                  "driven sys.path", RuntimeWarning)
else:
    from openerp.cli import server as startup
    from openerp.tools import config
    from openerp import SUPERUSER_ID
    from openerp.tools.parse_version import parse_version

from optparse import OptionParser  # we support python >= 2.6

logger = logging.getLogger(__name__)

DEFAULT_VERSION_PARAMETER = 'buildout.db_version'

DEFAULT_VERSION_FILE = 'VERSION.txt'


class OpenERPVersion(Version):
    """OpenERP idea of version, wrapped in a class.

    Provides straight-ahead comparison with tuples of integers, or
    distutils Version classes.
    """

    def parse(self, incoming):
        if isinstance(incoming, OpenERPVersion):
            self.vstring = incoming.vstring
            self.components = incoming.components
        else:
            self.vstring = incoming
            self.components = parse_version(incoming)

    def __str__(self):
        return self.vstring

    def __repr__(self):
        return 'OpenERPVersion(%r)' % str(self)

    def __cmp__(self, other):
        if isinstance(other, tuple):
            other = '.'.join(str(s) for s in other)
        elif not isinstance(other, self.__class__):
            other = str(other)  # Works with distutils' Version classes

        other = self.__class__(other)
        return cmp(self.components, other.components)


class Session(object):
    """A class to represent the server object.

    you should have exactly one per process.

    Before actual use, call the ``bootstrap`` method.
    Then you have useful attributes/methods behaving like unit test classes:

    :``cr``: a cursor
    :``uid`:` user id
    :``db_version``: version of this installation stored in database (settable,
                     meant for upgrade logic)
    :``package_version``: version of this installation read from VERSION file.

    Instantiation is done by passing the path to OpenERP main
    configuration file and the path of the buildout directory.

    Later versions of the recipe may find a way to pass the whole buildout
    configuration (recall that this is to be used in a separate process in
    which the buildout configuration has not been parsed).
    """

    def __init__(self, conffile, buildout_dir, parse_config=True):
        self.buildout_dir = buildout_dir
        self.openerp_config_file = conffile

        self._registry = self.cr = None
        if parse_config:
            config.parse_config(['-c', conffile])

    def ready(self):
        return self._registry is not None

    def open(self, db=None):
        """Load the database

        if the database is not specified, the same cascading as OpenERP
        mainstream will be applied: configuration file, psycopg2/lipq defaults.
        """
        if db is None:
            db = config['db_name']
        if not db:
            db = ''  # expected value expected by OpenERP to start defaulting.
        startup.check_root_user()
        startup.check_postgres_user()
        openerp.netsvc.init_logger()
        self._registry = openerp.modules.registry.RegistryManager.get(
            db, update_module=False)
        self.init_cursor()
        self.uid = SUPERUSER_ID

    def _version_parameter_name(self):
        # A latter version may read the buildout configuration.
        return DEFAULT_VERSION_PARAMETER

    def _version_file_path(self):
        # A latter version may read the buildout configuration.
        return os.path.join(self.buildout_dir, DEFAULT_VERSION_FILE)

    @property
    def db_version(self):
        """Return the version number stored in DB for the whole buildout.

        This can be thought as the latest version to which the DB has been
        upgraded to.
        A simple caching system to avoid querying the DB multiple times is
        implemented.
        """
        db_version = getattr(self, '_db_version', None)
        if db_version is not None:
            return db_version

        db_version = self.registry('ir.config_parameter').get_param(
            self.cr, self.uid, self._version_parameter_name())
        if not db_version:
            # as usual OpenERP thinks its simpler to use False as None
            # restoring sanity ASAP
            db_version = None
        else:
            db_version = OpenERPVersion(db_version)
        self._db_version = db_version
        return db_version

    @db_version.setter
    def db_version(self, version):
        self.registry('ir.config_parameter').set_param(
            self.cr, self.uid, self._version_parameter_name(), str(version))
        self._db_version = OpenERPVersion(version)

    @property
    def package_version(self):
        """Read the version file from buildout directory.

        Comments introduced with a hash are accepted.
        Only the first significant line is taken into account.
        """
        pkg_version = getattr(self, '_pkg_version', None)
        if pkg_version is not None:
            return pkg_version

        with open(self._version_file_path()) as f:
            for line in f:
                line = line.split('#', 1)[0].strip()
                if not line:
                    continue
                self._pkg_version = OpenERPVersion(line)
                return self._pkg_version

    def update_modules_list(self):
        """Update the list of available OpenERP modules, like the UI allows to.

        This is necessary prior to install of any new module.
        """
        self.registry('ir.module.module').update_list(self.cr, self.uid)

    def init_cursor(self):
        self.cr = self._registry.db.cursor()

    def registry(self, model):
        """Return the model object."""
        return self._registry.get(model)

    def rollback(self):
        self.cr.rollback()

    def close(self):
        dbname = self.cr.dbname
        self.cr.close()
        openerp.modules.registry.RegistryManager.delete(dbname)

    def update_modules(self, modules, db=None):
        """Update the modules in the database.

        If the database is not specified, it is assumed to have already
        been opened with ``open()``, for instance to check versions.

        If it is specified, then the session in particular opens that db and
        will use it afterwards whether another one was already opened or not.
        """
        if db is None:
            if self.cr is None:
                raise ValueError("update_modules needs either the session to "
                                 "be opened or an explicit database name")
            db = self.cr.dbname

        if self.cr is not None:
            self.close()
        for module in modules:
            config['update'][module] = 1
        self._registry = openerp.modules.registry.RegistryManager.get(
            db, update_module=True)
        config['update'].clear()
        self.init_cursor()

    def install_modules(self, modules, db=None, with_demo=False):
        """Install the modules in the database.

        If the database is not specified, it is assumed to have already
        been opened with ``open()``, for instance to check versions.

        If it is specified, then the session in particular opens that db and
        will use it afterwards whether another one was already opened or not.
        """
        if db is None:
            if self.cr is None:
                raise ValueError("install_modules needs either the session to "
                                 "be opened or an explicit database name")
            db = self.cr.dbname

        if self.cr is not None:
            self.close()
        config['without_demo'] = not with_demo
        for module in modules:
            config['init'][module] = 1
        self._registry = openerp.modules.registry.RegistryManager.get(
            db, update_module=True, force_demo=with_demo)
        config['init'].clear()
        self.init_cursor()

    def handle_command_line_options(self, to_handle):
        """Handle prescribed command line options and eat them.

        Anything before first occurrence of '--' is ours and removed from
        sys.argv.

        Help messages:

        If -h or --help is specified  and -- is not, the help for the wrapper
        will be printed, and the -h/--help option kept in sys.argv.

        If -h or --help is specified before --, the help for this wrapper will
        be printed and options after -- will be kept in sys.argv.

        if -h or --help is specified after --, it will be ignored at this
        stage, and kept in sys.argv (in most cases triggering help print for
        the wrapped script).
        """

        parser = OptionParser(
            usage="%(prog)s [OpenERP options] -- other arguments",
            description="This is a script rewrapped by OpenERP buildout "
                        "recipe to add OpenERP-related options on the command "
                        "line prior to other arguments.")

        if '-d' in to_handle:
            parser.add_option('-d', '--db-name',
                              help="Name of the database to work on. "
                              "If not specified, the database from "
                              "configuration files will be used")

        try:
            sep = sys.argv.index('--')
        except ValueError:
            if '-h' in sys.argv or '--help' in sys.argv:
                # in case of call myscript -h --, only the wrapper help
                # will be printed
                parser.epilog = ("Help message from the wrapped script, "
                                 "if any, will follow.")
                parser.print_help()
                print
                return
            our_argv = []
            sep = None
        else:
            our_argv = sys.argv[1:sep]

        options, args = parser.parse_args(our_argv)

        if sep is not None:
            del sys.argv[1:sep+1]

        if '-d' in to_handle:
            if options.db_name:
                logger.info("Opening database %r", options.db_name)
            else:
                logger.info("No database specified, using the one specified "
                            "in buildout configuration.")
            self.open(db=options.db_name)

_imported_addons = set()


def already_imported(module_name):
    name = module_name.rsplit('.', 1)[-1]
    if name in _imported_addons:
        return True
    _imported_addons.add(name)
    return False


def clear_import_registry():
    _imported_addons.clear()
