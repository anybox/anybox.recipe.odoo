from unittest import TestCase
from anybox.recipe.odoo.runtime.session import Session
try:
    from odoo.tests.common import get_db_name
    from odoo.release import version_info
except ImportError:
    from openerp.tests.common import get_db_name
    from openerp.release import version_info

TEST_MODULE = 'report'


class SessionTestCase(TestCase):

    def setUp(self):
        super(SessionTestCase, self).setUp()
        self.open_session()
        # This could be cleaner as uninstall module is not only a state but
        # removing db structure and data, but at that time the state of the
        # module is the only thing we care in this state so we don't needs to
        # reload the session twice
        report_module = self.session.env['ir.module.module'].search(
            [('name', '=', TEST_MODULE)]
        )
        report_module.state = 'uninstalled'

    def tearDown(self):
        self.session.close()
        super(SessionTestCase, self).tearDown()

    def open_session(self):
        self.session = Session(None, None, parse_config=False)
        self.session.open(db=get_db_name())

    def test_env_after_install_module(self):
        self.assertAdminPresentWithV8API()
        self.session.install_modules([TEST_MODULE])
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
        self.session.install_modules([TEST_MODULE])
        self.assertTrue(self.session.env.context.get('tz'))

    def test_registry(self):
        # If version 8, 9 registry should be working
        self.assertAdminPresentWithV8API()
        if version_info[0] >= 10:
            # Type error because we a registry exists and return
            # an odoo.api.res.users class which does not know about
            # old api signature methods, we are getting an error likes::
            #
            #    TypeError: unbound method search() must be called with
            #    res.users instance as first argument (got Cursor instance
            #    instead)
            with self.assertRaises(TypeError):
                self.assertAdminPresentWithV7API()
        else:
            self.assertAdminPresentWithV7API()

    def assertModuleState(self, module_name, expected_state):
        self.assertEqual(
            expected_state,
            self.session.env['ir.module.module'].search(
                [('name', '=', module_name)]
            ).state
        )

    def test_insall_module(self):
        self.assertModuleState('report', 'uninstalled')
        self.session.install_modules([TEST_MODULE])
        self.assertModuleState('report', 'installed')
