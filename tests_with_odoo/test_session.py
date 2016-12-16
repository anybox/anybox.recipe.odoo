from unittest import TestCase
from anybox.recipe.odoo.runtime.session import Session
try:
    from odoo.tests.common import get_db_name
    from odoo.release import version_info
except ImportError:
    from openerp.tests.common import get_db_name
    from openerp.release import version_info


class SessionTestCase(TestCase):

    def setUp(self):
        super(SessionTestCase, self).setUp()
        self.open_session()

    def tearDown(self):
        self.session.close()

    def open_session(self):
        self.session = Session(None, None, parse_config=False)
        self.session.open(db=get_db_name())

    def test_env_after_install_module(self):
        self.assertAdminPresentWithV8API()
        self.session.install_modules(['report'])
        self.assertAdminPresentWithV8API()

    def assertAdminPresentWithV7API(self):
        user_mdl = self.session.registry('res.users')
        admin_id = user_mdl.search(
            self.session.cr, self.session.uid, [('login', '=', 'admin')]
        )[0]

        self.assertEqual(
            u"Administrator",
            user_mdl.read(
                self.session.cr, self.session.uid, admin_id, ['name']
            )['name']
        )

    def assertAdminPresentWithV8API(self):
        self.assertEqual(
            u"Administrator",
            self.session.env['res.users'].search(
                [('login', '=', 'admin')]
            ).name
        )

    def test_env_context(self):
        self.assertTrue(self.session.env.context.get('tz'))
        self.session.install_modules(['web_tests'])
        self.assertTrue(self.session.env.context.get('tz'))

    def test_registry(self):
        # If version 8, 9 registry should be working
        self.assertAdminPresentWithV8API()
        if version_info[0] >= 10:
            self.assertAdminPresentWithV7API()
        else:
            self.assertAdminPresentWithV7API()
