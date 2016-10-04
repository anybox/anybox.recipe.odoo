import os
from odoo.tests.common import TransactionCase
from anybox.recipe.odoo.runtime.session import Session

TEST_DATA_DIR = os.path.join(os.path.dirname(__file__), 'data')


class VersionTestCase(TransactionCase):

    def setUp(self):
        super(VersionTestCase, self).setUp()
        self.initSession()

    def initSession(self):
        session = self.session = Session(None, None, parse_config=False)
        session.registry = self.registry
        session.cr = self.cr
        session.uid = self.uid
        session.buildout_dir = TEST_DATA_DIR
        return session

    def test_version_class(self):
        """Test the version class itself.

        This does not need a database, but still needs to import Openerp"""
        version = self.session.parse_version_string('1.2.3')
        self.assertFalse(version < '1.2.2')
        self.assertTrue(version < (1, 2, 5))
        self.assertTrue(version < '1.2.4-dev')
        self.assertFalse(version < '1.2.3a1-2')
        self.assertTrue(version < '1.2.4a1-2')

    def test_db_version(self):
        session = self.session
        session.db_version = '1.2.3a3'
        self.assertEqual(str(session.db_version), '1.2.3a3')

        session = self.initSession()
        self.assertEqual(str(session.db_version), '1.2.3a3')
        self.assertTrue(session.db_version < '1.2.3')
        self.assertTrue(session.db_version < (1, 2, 3))
        self.assertTrue(session.db_version > (1, 2, 2))

    def test_db_version_missing(self):
        self.assertTrue(self.session.db_version is None)

    def test_pkg_version(self):
        pkg_version = self.session.package_version
        self.assertEqual(pkg_version, '0.1.2-dev')
        self.assertTrue(pkg_version > (0, 1, 1))
        self.assertTrue(pkg_version < (0, 1, 2))

        # The assertRaises context manager appears in Python 2.7
        try:
            self.session.package_version = '1.2.3'
        except AttributeError:
            pass
        else:
            self.fail("package_version should be readonly")
