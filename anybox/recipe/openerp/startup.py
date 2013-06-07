"""Utilities to start a server process."""
import warnings
try:
    import openerp
except ImportError:
    warnings.warn("This must be imported with a buildout openerp recipe "
                  "driven sys.path", RuntimeWarning)
else:
    from openerp.cli import server as startup
    from openerp.tools import config


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
