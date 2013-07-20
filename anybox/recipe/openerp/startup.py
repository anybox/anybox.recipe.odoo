"""Utilities to start a server process."""
import warnings
import sys
import logging
try:
    import openerp
except ImportError:
    warnings.warn("This must be imported with a buildout openerp recipe "
                  "driven sys.path", RuntimeWarning)
else:
    from openerp.cli import server as startup
    from openerp.tools import config
from optparse import OptionParser  # we support python >= 2.6

logger = logging.getLogger(__name__)


class Session(object):
    """A class to represent the server object.

    you should have exactly one per process.

    Before actual use, call the ``bootstrap`` method.
    Then you have useful attributes/methods behaving like unit test classes:

    self.cr: a cursor
    self.uid: user id
    """

    def __init__(self, conffile):
        self._registry = self.cr = None
        config.parse_config(['-c', conffile])

    def ready(self):
        return self._registry is not None

    def open(self, db=None):
        if db is None:
            db = config['db_name']
        startup.check_root_user()
        startup.check_postgres_user()
        openerp.netsvc.init_logger()
        self._registry = openerp.modules.registry.RegistryManager.get(
            db, update_module=False)
        self.init_cursor()

    def init_cursor(self):
        self.cr = self._registry.db.cursor()

    def registry(self, model):
        """Return the model object."""
        return self._registry.get(model)

    def rollback(self):
        self.cr.rollback()

    def close(self):
        self.cr.close()

    def handle_command_line_options(self, to_handle):
        """Handle prescribed command line options and eat them.

        Anything before first occurrence of '--' is ours and removed from
        sys.argv
        """
        try:
            sep = sys.argv.index('--')
        except ValueError:
            return

        our_argv = sys.argv[1:sep]
        parser = OptionParser()
        # TODO add more
        if '-d' in to_handle:
            parser.add_option('-d', '--db-name',
                              help='Name of the database to work on.')

        options, args = parser.parse_args(our_argv)
        del sys.argv[1:sep+1]

        if options.db_name:
            logger.info("Opening database %r", options.db_name)
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
