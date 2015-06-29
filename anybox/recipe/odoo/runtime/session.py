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
    try:
        from openerp.cli import server as startup
    except ImportError:
        from .backports.cli import server as startup
    from openerp.tools import config
    from openerp import SUPERUSER_ID
    from openerp.tools.parse_version import parse_version

from optparse import OptionParser  # we support python >= 2.6

logger = logging.getLogger(__name__)

DEFAULT_VERSION_PARAMETER = 'buildout.db_version'

DEFAULT_VERSION_FILE = 'VERSION.txt'


class OpenERPVersion(Version):
    """Odoo idea of version, wrapped in a class.

    This is based on :meth:`openerp.tools.parse_version`, and
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
    """A class to give server-level access to one database.

    There should be exactly one instance of this class per process.
    It can be used for any kind of script involving Odoo API, and provides
    facilities for upgrade scripts (see also
    :mod:anybox.recipe.odoo.runtime.upgrade)

    Before actual use, call :meth:`open`.
    Then you'll have useful attributes and methods reminiscent of the unit test
    classes:

    * :attr:`cr`: a cursor
    * :attr:`uid`: user id
    * :attr:`registry`: access to model objects
    * :attr:`is_initialization`: True if and only if the database was not
      initialized before the call to :meth:`open`

    Example application code::

       session.open(db_name="my_db")
       admin = session.registry('res_users').browse(session.cr, session.uid, 1)
       (...)
       session.cr.commit()
       session.close()

    Transaction management is up to user code

    Upgrade scripts writers should check the version handling properties:

    * :meth:`db_version`
    * :meth:`package_version`

    Instantiation is done by passing the path to Odoo main
    configuration file and the path of the buildout directory.

    Usually, instantiation code is written by the recipe in the body of the
    executable "Odoo scripts" it produces.
    Script writers provide a callable that takes a
    :class:`.Session` object argument and declare it as a console script entry
    point in their distribution.
    End users can reference such entry points in their buildout configurations
    to have buildout produce the actual executable. See :doc:`/scripts`
    for details.

    Upgrade scripts are a special case of that process, in which the entry
    point is actually provided by the recipe and rewraps a user-level
    source script.

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

    def open(self, db=None, with_demo=False):
        """Load the database

        Loading an empty database in Odoo has the side effect of installing
        the ``base`` module. Whether to loading demo data or not has therefore
        to be decided right away.

        :param db: database name. If not specified, the same cascading of
                   defaults as Odoo mainstream will be applied:
                   configuration file, psycopg2/lipq defaults.
        :param with_demo: controls the loading of demo data for all
                          module installations triggered by this call to
                          :meth:`open` and further uses of :meth:`load_modules`
                          on this :class:`Session` instance:

                          * if ``True``, demo data will uniformly be loaded
                          * if ``False``, no demo data will be loaded
                          * if ``None``, demo data will be loaded according to
                            the value of ``without_demo`` in configuration

                          In all cases, the behaviour will stay consistent
                          until the next call of ``open()``, but the
                          implementation does not protect against any race
                          conditions in Odoo internals.
        """
        if db is None:
            db = config['db_name']
        if not db:
            db = ''  # expected value expected by Odoo to start defaulting.

        cnx = openerp.sql_db.db_connect(db)
        cr = cnx.cursor()
        self.is_initialization = not(openerp.modules.db.is_initialized(cr))
        cr.close()

        startup.check_root_user()
        startup.check_postgres_user()
        openerp.netsvc.init_logger()

        saved_without_demo = config['without_demo']
        if with_demo is None:
            with_demo = config['without_demo']

        config['without_demo'] = not with_demo
        self.with_demo = with_demo

        self._registry = openerp.modules.registry.RegistryManager.get(
            db, update_module=False)
        config['without_demo'] = saved_without_demo
        self.init_cursor()
        self.uid = SUPERUSER_ID
        self.init_environments()
        self.context = self.registry('res.users').context_get(
            self.cr, self.uid)
        if hasattr(openerp, 'api'):
            self.env = openerp.api.Environment(self.cr, self.uid, self.context)

    def init_environments(self):
        """Enter the environments context manager, but don't leave it

        Automatically called by :meth:`open` and registry altering methods.
        See :class:``openerp.api.Environment`` for explanations about
        environments.

        For OpenERP/Odoo versions prior to the new style API merge, this
        is a no-op.

        This thread-local ``environments`` is initialized and cleaned with
        each request in the normal usage of the framework.
        That's why is is provided as a context manager.

        Therefore, user code probably needs in some case to clean it to avoid
        side effects. This can be done by calling :meth:`clean_environments`.
        """
        try:
            gen_factory = openerp.api.Environment.manage
        except AttributeError:
            return

        self._environments_gen_context = gen_factory().gen
        self._environments_gen_context.next()

    def clean_environments(self, reinit=True):
        """Cleans the thread-local environment.

        See :meth:`init_environments` for more details.
        This method does nothing if the environments have not been initialized.

        :param bool reinit: if ``True``, :meth:`init_environments` will be
                            called again after cleaning
        """
        try:
            gen_context = self._environments_gen_context
        except AttributeError:
            return

        try:
            gen_context.next()
        except StopIteration:
            pass
        else:
            logger.warn("clean_environments: we had the context manager, but "
                        "it had not been called. This suggest low-leve "
                        "tampering with it that should be more cautious. "
                        "Proceeding with cleansing.")
            try:
                gen_context.next()
            except StopIteration:
                pass
            else:
                raise RuntimeError("Called the environments context manager "
                                   "twice and it's not finished. "
                                   "This is really unexpected.")
        del self._environments_gen_context
        if reinit:
            self.init_environments()

    # A later version might read that from buildout configuration.
    _version_parameter_name = DEFAULT_VERSION_PARAMETER

    @property
    def version_file_path(self):
        """Absolute path of the flat file storing the package version.

        For now this is not configurable, a later version might read it
        from buildout configuration.
        """
        return os.path.join(self.buildout_dir, DEFAULT_VERSION_FILE)

    def parse_version_string(self, vstring):
        """Stable method for downstream code needing to instantiate a version.

        This method returns an appropriate version instance, without
        any dependency on where to import the class from. Especially useful
        for applications whose life started before this set of utilities has
        been used : this helps building an usable default.
        """
        return OpenERPVersion(vstring)

    @property
    def db_version(self):
        """Settable property for version stored in DB of the whole buildout.

        This can be thought as the latest version to which the DB has been
        upgraded to.
        A simple caching system to avoid querying the DB multiple times is
        implemented.
        """
        db_version = getattr(self, '_db_version', None)
        if db_version is not None:
            return db_version

        db_version = self.registry('ir.config_parameter').get_param(
            self.cr, self.uid, self._version_parameter_name)
        if not db_version:
            # as usual Odoo thinks its simpler to use False as None
            # restoring sanity ASAP
            db_version = None
        else:
            db_version = OpenERPVersion(db_version)
        self._db_version = db_version
        return db_version

    @db_version.setter
    def db_version(self, version):
        self.registry('ir.config_parameter').set_param(
            self.cr, self.uid, self._version_parameter_name, str(version))
        self._db_version = OpenERPVersion(version)

    @property
    def package_version(self):
        """Property reading the version file from buildout directory.

        Comments introduced with a hash are accepted.
        Only the first significant line is taken into account.
        """
        pkg_version = getattr(self, '_pkg_version', None)
        if pkg_version is not None:
            return pkg_version

        try:
            with open(self.version_file_path) as f:
                for line in f:
                    line = line.split('#', 1)[0].strip()
                    if not line:
                        continue
                    self._pkg_version = OpenERPVersion(line)
                    return self._pkg_version
        except IOError:
            logger.info("No version file could be read, "
                        "package version considered to be None")

    def update_modules_list(self):
        """Update the list of available Odoo modules, like the UI allows to.

        This is necessary prior to install of any new module.
        """
        self.registry('ir.module.module').update_list(self.cr, self.uid)

    def init_cursor(self):
        db = getattr(self._registry, 'db', None)
        if db is None:  # current trunk (future v8)
            self.cr = self._registry.cursor()
        else:
            # In OpenERP < 8, Registry.cursor() object is
            # a context manager providing auto closing,
            # but we don't want to control the whole lifespan
            # of the cursor.
            self.cr = db.cursor()

    def registry(self, model):
        """Lookup model by name and return a ready-to-work instance."""
        return self._registry.get(model)

    def rollback(self):
        self.cr.rollback()
        self.clean_environments()

    def is_cursor_closed(self):
        """Compatibility wrapper.

        On OpenERP 7, the attribute is ``__closed`` but can't even be accessed
        if the cursor is closed (``OperationalError`` is raised systematically
        in ``sql_db``)

        On Odoo 8, the attribute is ``_closed`` and works correctly.
        """
        return any(self.cr.__dict__.get(c)
                   for c in ('_Cursor__closed', '_closed'))

    def close(self):
        """Close the cursor and forget about the current database.

        The session is thus ready to open another database.
        This methods should be idempotent, wouldn't fail if the cursor is
        already closed or the current database is not in registry (either
        already deleted, or could not be opened at all)
        """
        dbname = self.cr.dbname
        if not self.is_cursor_closed():
            self.cr.close()
        self.clean_environments()
        # GR: I did check that implementation is designed not to fail
        # on Odoo 8 and OpenERP 7
        openerp.modules.registry.RegistryManager.delete(dbname)

    def update_modules(self, modules, db=None):
        """Update the prescribed modules in the database.

        :param db: Database name. If not specified, it is assumed to have
                   already been opened with :meth:`open`, e.g, for a prior
                   read of :meth:`db_version`.
                   If it is specified, then the session in particular opens
                   that db and will use it afterwards whether another one
                   was already opened or not.
        :param modules: any iterable of module names.
                        Not installed modules will be ignored
                        The special name ``'all'`` triggers the update of
                        all installed modules.
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
        self.clean_environments()

    def install_modules(self, modules, db=None, update_modules_list=True,
                        open_with_demo=False):
        """Install the modules in the database.

        Has the side effect of closing the current cursor, committing if and
        only if the list of modules is updated.

        Demo data loading is handled consistently with the decision taken
        by :meth:`open`.

        :param db: Database name. If not specified, it is assumed to have
                   already been opened with :meth:`open`, e.g, for a prior
                   read of :meth:`db_version`.
                   If it is specified, then the session in particular opens
                   that db and will use it afterwards whether another one
                   was already opened or not.
        :param modules: any iterable of module names.
        :param update_modules_list: if True, will update the module lists
                                    *and commit* before the install begins.
        :param open_with_demo: if ``db`` is not None, will be passed to
                               :meth:`open`.
        """
        already_open = self.cr is not None
        if db is None:
            if not already_open:
                raise ValueError("install_modules needs either the session to "
                                 "be opened or an explicit database name")
            db = self.cr.dbname
        elif update_modules_list and not (
                already_open and self.cr.dbname == db):
            self.open(db=db, with_demo=open_with_demo)

        if update_modules_list:
            self.update_modules_list()
            self.cr.commit()

        if self.cr is not None:
            self.close()
        saved_without_demo = config['without_demo']

        # with update_modules_list=False, an explicitely named DB would not
        # have gone through open() yet.
        config['without_demo'] = not getattr(self, 'with_demo', open_with_demo)
        for module in modules:
            config['init'][module] = 1
        self._registry = openerp.modules.registry.RegistryManager.get(
            db, update_module=True, force_demo=self.with_demo)
        config['init'].clear()
        config['without_demo'] = saved_without_demo
        self.init_cursor()
        self.clean_environments()

    def ref(self, external_id):
        """Return ir.model.data object id from its external identifier.

        :param external_id: External identifier of form module.name.
                            e.g. base.user_root
        :raise: ValueError if not found or external_id malformed
        """
        if '.' not in external_id:
            raise ValueError(
                "ref requires a fully qualified parameter: 'module.identifier'"
            )
        ir_model_data = self.registry('ir.model.data')
        module, name = external_id.split('.', 1)
        _, ref_id = ir_model_data.get_object_reference(
            self.cr, self.uid, module, name
        )
        return ref_id

    def browse_ref(self, external_id):
        """Return ir.model.data browse object from its external identifier.

        :param external_id: External identifier of form module.name.
                            e.g. base.user_root
        :raise: ValueError if not found or external_id malformed
        """
        if '.' not in external_id:
            raise ValueError(
                "browse_ref requires a fully qualified parameter: "
                "'module.identifier'"
            )
        ir_model_data = self.registry('ir.model.data')
        module, name = external_id.split('.', 1)
        return ir_model_data.get_object(self.cr, self.uid, module, name)

    def handle_command_line_options(self, to_handle):
        """Handle prescribed command line options and eat them.

        Anything before first occurrence of ``--`` on the command-line is taken
        into account and removed from ``sys.argv``.

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
            usage="%(prog)s [Odoo options] -- other arguments",
            description="This is a script rewrapped by Odoo buildout "
                        "recipe to add Odoo-related options on the command "
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
