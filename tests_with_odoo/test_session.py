from unittest import TestCase
from anybox.recipe.odoo.runtime.session import Session
from odoo.tests.common import get_db_name


class SessionTestCase(TestCase):

    def setUp(self):
        super(SessionTestCase, self).setUp()
        self.session = Session(None, None, parse_config=False)

    def open_session(self):
        self.session.open(db=get_db_name())

    def test_env_after_install_module(self):
        self.open_session()
        self.assertAdminPresentWithV8API()
        self.session.install_modules(['report'])
        self.assertAdminPresentWithV8API()
        self.session.close()

    def assertAdminPresentWithV8API(self):
        self.assertEqual(
            u"Administrator",
            self.session.env['res.users'].search([('login', '=', 'admin')]).name
        )

    def test_env_context(self):
        self.open_session()
        self.assertTrue(self.session.env.context.get('tz'))
        self.session.install_modules(['web_tests'])
        self.assertTrue(self.session.env.context.get('tz'))
        self.session.close()
