import os
from openerp.tests.common import TransactionCase
from anybox.recipe.openerp.startup import Session

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

    def test_db_version(self):
        session = self.session
        session.db_version = '1.2.3a3'
        self.assertEqual(str(session.db_version), '1.2.3a3')

        session = self.initSession()
        self.assertEqual(str(session.db_version), '1.2.3a3')
        self.assertTrue(session.db_version < '1.2.3')
        self.assertTrue(session.db_version < (1, 2, 3))
        self.assertTrue(session.db_version > (1, 2, 2))

    def test_pkg_version(self):
        pkg_version = self.session.package_version
        self.assertEqual(pkg_version, '0.1.2-dev')
        self.assertTrue(pkg_version > (0, 1, 1))
        self.assertTrue(pkg_version < (0, 1, 2))
