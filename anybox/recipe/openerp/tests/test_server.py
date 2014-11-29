"""Test the server recipe.

NB: zc.buildout.testing provides utilities for integration tests, with
an embedded http server, etc.
"""
import os
from pkg_resources import Requirement

from ..base import MissingDistribution
from ..base import IncompatibleConstraintError
from ..base import IncompatibleVersionError
from anybox.recipe.openerp.server import ServerRecipe
from anybox.recipe.openerp.testing import get_vcs_log
from anybox.recipe.openerp.testing import RecipeTestCase
from zc.buildout import UserError

TEST_DIR = os.path.dirname(__file__)


class TestServer(RecipeTestCase):

    def make_recipe(self, name='openerp', **options):
        self.recipe = ServerRecipe(self.buildout, name, options)

    def test_retrieve_addons_local(self):
        """Setting up a local addons line."""
        addons_dir = os.path.join(self.buildout_dir, 'addons-custom')
        self.make_recipe(version='6.1', addons='local addons-custom')

        self.recipe.retrieve_addons()
        paths = self.recipe.addons_paths
        self.assertEquals(get_vcs_log(), [])
        self.assertEquals(paths, [addons_dir])

    def test_retrieve_addons_local_standalone(self):
        """A local standalone addon is not permitted."""
        addons_dir = os.path.join(self.buildout_dir, 'addons-custom')
        os.mkdir(addons_dir)
        with open(os.path.join(addons_dir, '__openerp__.py'), 'w') as f:
            f.write("#Empty python package")
        self.make_recipe(version='6.1', addons='local addons-custom')
        self.assertRaises(UserError, self.recipe.retrieve_addons)

    def test_retrieve_addons_local_options(self):
        """Addons options work for 'local' by testing (useless) subdir option.
        """
        custom_dir = os.path.join(self.buildout_dir, 'custom')
        addons_dir = os.path.join(custom_dir, 'addons')
        self.make_recipe(version='6.1', addons='local custom subdir=addons')

        self.recipe.retrieve_addons()
        paths = self.recipe.addons_paths
        self.assertEquals(get_vcs_log(), [])
        self.assertEquals(paths, [addons_dir])

    def test_retrieve_addons_vcs(self):
        """A VCS line in addons."""
        self.make_recipe(version='6.1', addons='fakevcs http://trunk.example '
                         'addons-trunk rev')
        # manual creation because fakevcs does nothing but retrieve_addons
        # has assertions on existence of target directories
        addons_dir = os.path.join(self.buildout_dir, 'addons-trunk')

        self.recipe.retrieve_addons()
        paths = self.recipe.addons_paths
        self.assertEquals(
            get_vcs_log(), [
                (addons_dir, 'http://trunk.example', 'rev',
                 dict(offline=False, clear_locks=False, clean=False)
                 )])
        self.assertEquals(paths, [addons_dir])

    def test_retrieve_addons_vcs_2(self):
        """Two VCS lines in addons."""
        self.make_recipe(version='6.1', addons=os.linesep.join((
            'fakevcs http://trunk.example addons-trunk rev',
            'fakevcs http://other.example addons-other 76')))
        # manual creation because fakevcs does nothing but retrieve_addons
        # has assertions on existence of target directories
        addons_dir = os.path.join(self.buildout_dir, 'addons-trunk')
        other_dir = os.path.join(self.buildout_dir, 'addons-other')

        self.recipe.retrieve_addons()
        paths = self.recipe.addons_paths
        self.assertEquals(
            get_vcs_log(), [
                (addons_dir, 'http://trunk.example', 'rev',
                 dict(offline=False, clear_locks=False, clean=False)),
                (other_dir, 'http://other.example', '76',
                 dict(offline=False, clear_locks=False, clean=False)),
            ])
        self.assertEquals(paths, [addons_dir, other_dir])

    def test_retrieve_addons_vcs_order(self):
        """Ordering of addons paths is respected."""
        self.make_recipe(
            version='6.1',
            addons=os.linesep.join(
                ['fakevcs http://trunk.example addons-%d rev' % d
                 for d in range(10)]))

        self.recipe.retrieve_addons()
        paths = self.recipe.addons_paths
        expected = [os.path.join(self.buildout_dir, 'addons-%d') % d
                    for d in range(10)]

        # fail only for ordering issues
        if set(paths) == set(expected):
            self.assertEqual(paths, expected)

    def test_retrieve_addons_subdir(self):
        self.make_recipe(version='6.1', addons='fakevcs lp:openerp-web web '
                         'last:1 subdir=addons bzrinit=branch')
        # manual creation because fakevcs does nothing but retrieve_addons
        # has assertions on existence of target directories
        web_dir = os.path.join(self.buildout_dir, 'web')
        web_addons_dir = os.path.join(web_dir, 'addons')

        self.recipe.retrieve_addons()
        paths = self.recipe.addons_paths
        self.assertEquals(get_vcs_log(), [
                          (web_dir, 'lp:openerp-web', 'last:1',
                           dict(offline=False, clear_locks=False, clean=False,
                                    subdir="addons", bzrinit="branch"))
                          ])
        self.assertEquals(paths, [web_addons_dir])

    def test_retrieve_addons_standalone_grouped(self):
        self.make_recipe(version='6.1', addons='fakevcs lp:my-addons1 addons1 '
                         'last:1 group=grouped\nfakevcs lp:my-addons2 addons2 '
                         'last:1 group=grouped')
        # manual creation because fakevcs does nothing but retrieve_addons
        # has assertions on existence of target directories
        group_dir = os.path.join(self.buildout_dir, 'grouped')
        addons1_dir = os.path.join(group_dir, 'addons1')
        addons2_dir = os.path.join(group_dir, 'addons2')

        self.recipe.retrieve_addons()
        paths = self.recipe.addons_paths
        self.assertEquals(get_vcs_log(), [
                          (addons1_dir, 'lp:my-addons1', 'last:1',
                           dict(offline=False, clear_locks=False, clean=False,
                                group="grouped")),
                          (addons2_dir, 'lp:my-addons2', 'last:1',
                           dict(offline=False, clear_locks=False, clean=False,
                                group="grouped"))
                          ])
        self.assertEquals(paths, [group_dir])

    def test_addons_standalone_oldstyle_prohibited(self):
        """Standalone addons must now be declared by the 'group' option."""
        dirname = 'standalone'
        self.make_recipe(version='6.1',
                         addons='fakevcs custom %s last:1' % dirname)
        dirname = dirname.rstrip('/')

        # manual creation of our single addon
        addon_dir = os.path.join(self.buildout_dir, dirname)
        os.mkdir(addon_dir)
        open(os.path.join(addon_dir, '__openerp__.py'), 'w').close()

        self.assertRaises(UserError, self.recipe.retrieve_addons)

    def test_retrieve_addons_clear_locks(self):
        """Retrieving addons with vcs-clear-locks option."""
        addons_dir = os.path.join(self.buildout_dir, 'addons')
        options = dict(version='6.1', addons='fakevcs lp:my-addons addons -1')
        options['vcs-clear-locks'] = 'True'
        self.make_recipe(**options)
        self.recipe.retrieve_addons()
        self.assertEquals(get_vcs_log(), [
                          (addons_dir, 'lp:my-addons', '-1',
                           dict(offline=False, clear_locks=True, clean=False))
                          ])

    def test_merge_requirements(self):
        self.make_recipe(version='6.1')
        self.recipe.version_detected = '6.1-1'
        self.recipe.merge_requirements()
        self.assertEquals(set(self.recipe.requirements),
                          set(['pychart', 'anybox.recipe.openerp',
                               'Pillow', 'openerp']))

    def test_merge_requirements_new_project_name(self):
        """At any point in time, Odoo is prone to change package name."""
        self.make_recipe(version='local %s' % os.path.join(
            TEST_DIR, 'odoo-project-renaming'))
        self.recipe.version_detected = '8.0'
        self.recipe.merge_requirements()
        self.assertEquals(set(self.recipe.requirements),
                          set(['pychart', 'anybox.recipe.openerp',
                               'Pillow', 'oodooo']))

    def test_merge_requirements_PIL(self):
        self.make_recipe(version='nightly trunk latest')
        self.recipe.version_detected = '6.2-nightly-20121110-003000'
        requirements = self.recipe.requirements
        requirements.append('PIL')
        self.recipe.merge_requirements()
        self.assertTrue('PIL' not in requirements)
        self.assertTrue('Pillow' in requirements)

    def test_merge_requirements_gunicorn(self):
        self.make_recipe(version='6.1', gunicorn='direct')
        self.recipe.version_detected = '6.1-1'
        self.recipe.apply_version_dependent_decisions()  # TODO make a helper
        self.recipe.merge_requirements()
        req = self.recipe.requirements
        self.assertTrue('gunicorn' in req)
        self.assertTrue('psutil' in req)

    def test_merge_requirements_devtools(self):
        self.make_recipe(version='6.1', with_devtools='true')
        self.recipe.version_detected = '6.1-1'
        self.recipe.merge_requirements()
        from anybox.recipe.openerp import devtools
        self.assertTrue(set(devtools.requirements).issubset(
            self.recipe.requirements))

    def test_merge_requirements_oe(self):
        self.make_recipe(version='nightly trunk 20121101',
                         with_devtools='true')
        self.recipe.version_detected = '7.0alpha'
        self.recipe.apply_version_dependent_decisions()
        self.recipe.merge_requirements()
        self.assertTrue('openerp-command' in self.recipe.requirements)

    def test_merge_requirements_oe_nodevtools(self):
        self.make_recipe(version='nightly trunk 20121101',
                         with_devtools='false')
        self.recipe.version_detected = '7.0alpha'
        self.recipe.merge_requirements()
        self.assertFalse('openerp-command' in self.recipe.requirements)

    def test_merge_requirements_oe_61(self):
        self.make_recipe(version='nightly 6.1 20121101',
                         with_devtools='true')
        self.recipe.version_detected = '6.1-20121101'
        self.recipe.merge_requirements()
        self.assertFalse('openerp-command' in self.recipe.requirements)

    def assertScripts(self, wanted):
        """Assert that scripts have been produced."""

        bindir = os.path.join(self.buildout_dir, 'bin')
        binlist = os.listdir(bindir)
        for script in wanted:
            if script not in binlist:
                self.fail("Script %r missing in bin directory." % script)

    def read_script(self, script_name):
        with open(os.path.join(self.buildout_dir, 'bin', script_name)) as f:
            return f.read()

    def test_retrieve_fixup_addons_local_61(self):
        addons_dir = os.path.join(self.buildout_dir, 'addons-custom')
        oerp_dir = os.path.join(TEST_DIR, 'oerp61')
        self.make_recipe(version='local %s' % oerp_dir,
                         addons='local addons-custom')

        self.recipe.version_detected = "6.1-20121003-233130"
        self.assertEquals(self.recipe.major_version, (6, 1))
        self.recipe.retrieve_addons()
        paths = self.recipe.addons_paths
        self.recipe.finalize_addons_paths(check_existence=False)
        self.assertEquals(paths, [os.path.join(oerp_dir, 'openerp', 'addons'),
                                  addons_dir])

    def test_retrieve_fixup_addons_local_60_check_ok(self):
        oerp_dir = os.path.join(TEST_DIR, 'oerp60')
        self.make_recipe(version='local %s' % oerp_dir,
                         addons='local addons-custom',
                         )

        self.recipe.version_detected = "6.0.4"
        self.recipe.retrieve_addons()

        addons_dir = os.path.join(self.buildout_dir, 'addons-custom')
        root_dir = os.path.join(oerp_dir, 'bin', 'addons')
        os.mkdir(addons_dir)
        self.recipe.finalize_addons_paths()
        paths = self.recipe.addons_paths
        self.assertEqual(paths, [root_dir, addons_dir])
        self.assertEqual(self.recipe.options['options.root_path'],
                         os.path.join(oerp_dir, 'bin'))

    def test_retrieve_fixup_addons_check(self):
        """Test that existence check of addons paths is done."""
        oerp_dir = os.path.join(TEST_DIR, 'oerp60')
        self.make_recipe(version='local %s' % oerp_dir,
                         addons='local addons-custom',
                         )

        self.recipe.version_detected = "6.0.4"
        self.recipe.retrieve_addons()
        self.assertRaises(AssertionError, self.recipe.finalize_addons_paths)

    def test_forbid_addons_paths_option(self):
        oerp_dir = os.path.join(TEST_DIR, 'oerp60')
        self.make_recipe(version='local %s' % oerp_dir,
                         addons='local addons-custom',
                         )
        self.recipe.options['options.addons_path'] = '/tmp/some/addon'
        self.recipe.version_detected = "6.0.4"
        self.assertRaises(UserError, self.recipe.finalize_addons_paths,
                          check_existence=False)

    def install_scripts(self, extra_develop=None, setup_has_pil=False,
                        extra_requirements=()):
        """Helper for full integration tests again a typical OpenERP setup.py

        Uses a minimal set of dependencies, though
        """

        self.recipe.apply_version_dependent_decisions()
        develop = {'gunicorn': 'fake_gunicorn'}
        if extra_develop is not None:
            develop.update(extra_develop)

        # providing a babel package without resorting to PyPI
        self.recipe.develop(os.path.join(TEST_DIR, 'fake_babel'))
        self.recipe.install_recipe_requirements()

        # minimal way of providing eggs with console
        # script entry points and requiring them for script creation
        eggs = list(extra_requirements)
        for egg, src in develop.items():
            self.recipe.develop(os.path.join(TEST_DIR, src))
            eggs.append(egg)

        self.recipe.options['eggs'] = os.linesep.join(eggs)

        self.recipe.install_requirements()
        self.recipe.develop(self.recipe.openerp_dir,
                            setup_has_pil=setup_has_pil)

        bindir = os.path.join(self.buildout_dir, 'bin')
        os.mkdir(bindir)

        self.recipe._register_extra_paths()
        self.recipe._install_startup_scripts()

    def test_install_scripts_61(self):
        self.make_recipe(version='local %s' % os.path.join(TEST_DIR, 'oerp61'),
                         gunicorn='direct',
                         with_devtools='true')
        self.recipe.options['options.log_handler'] = ":INFO,werkzeug:WARNING"
        self.recipe.options['options.log_level'] = "WARNING"
        self.recipe.version_detected = "6.1-20121003-233130"

        self.install_scripts()
        self.assertScripts(('start_openerp',
                            'test_openerp',
                            'gunicorn_openerp',
                            'cron_worker_openerp',
                            ))

        with open(os.path.join(self.buildout_dir, 'etc',
                               'gunicorn_openerp.conf.py')) as gconf:
            s = gconf.read()
            self.assertTrue("[':INFO', 'werkzeug:WARNING']" in s)

    def test_install_scripts_60(self):
        self.make_recipe(version='local %s' % os.path.join(TEST_DIR, 'oerp60'),
                         with_devtools='true')
        self.recipe.options['options.log_level'] = "WARNING"
        self.recipe.version_detected = "6.0.4"

        self.install_scripts()
        self.assertScripts(('start_openerp',
                            'test_openerp',
                            ))

    def do_test_install_scripts_soft_deps(self, exc=None):
        """If a soft requirement is missing, the scripts are still generated.
        """
        self.make_recipe(version='local %s' % os.path.join(TEST_DIR, 'oerp61'),
                         gunicorn='direct',
                         with_devtools='true')
        self.recipe.version_detected = "6.1-20121003-233130"

        softreq = 'zztest-softreq'
        self.recipe.missing_deps_instructions[softreq] = (
            "This is an expected condition in this test.")
        self.recipe.soft_requirements = (softreq,)

        # offline won't be  enough, sadly for zc.buildout < 2.0
        self.recipe.b_options['offline'] = 'true'

        if exc is None:
            self.unreachable_distributions.add(softreq)
        else:
            self.exc_distributions[softreq] = exc

        self.install_scripts(extra_requirements=(softreq,))
        self.assertScripts(('start_openerp',
                            'test_openerp',
                            'gunicorn_openerp',
                            'cron_worker_openerp',
                            ))

    def test_install_scripts_indirect_soft_deps(self, exc=None):
        """If a requirement is soft and indirect, UserError is properly raised.
        """
        self.make_recipe(version='local %s' % os.path.join(TEST_DIR, 'oerp61'),
                         gunicorn='direct',
                         with_devtools='true')
        self.recipe.version_detected = "6.1-20121003-233130"

        somereq = 'zztest-req'
        softreq = 'zztest-softreq'
        self.recipe.missing_deps_instructions[softreq] = (
            "This is an expected condition in this test.")
        self.recipe.soft_requirements = (softreq,)

        self.recipe.b_options['offline'] = 'true'

        # the key fact is that the requirement that exc is about is not
        # in recipe.options['eggs']
        self.exc_distributions[somereq] = MissingDistribution(
            Requirement.parse(softreq), [])

        self.assertRaises(UserError, self.install_scripts,
                          extra_requirements=(somereq,))

    def test_install_scripts_soft_deps_missing_dist(self):
        self.do_test_install_scripts_soft_deps()

    def test_install_scripts_soft_deps_missing_dist_exc(self):
        req = Requirement.parse("zztest-softreq")
        self.do_test_install_scripts_soft_deps(
            exc=MissingDistribution(req, []))

    def test_install_scripts_soft_deps_incompatible_constraint(self):
        if IncompatibleConstraintError is None:  # zc.buildout < 1.7
            return  # @skip appears in py2.7

        req = Requirement.parse("zztest-softreq==1.2.3")
        self.do_test_install_scripts_soft_deps(
            exc=IncompatibleConstraintError('Bad constraint', '>2', req))

    def test_install_scripts_soft_deps_incompatible_constraint_reraise(self):
        if IncompatibleConstraintError is None:  # zc.buildout < 1.7
            return  # skipping infra is for py>2.7

        req = Requirement.parse("zztest-hardreq==1.2.3")
        exc = IncompatibleConstraintError('Bad constraint', '>2', req)
        try:
            self.do_test_install_scripts_soft_deps(exc=exc)
        except IncompatibleConstraintError as exc2:
            self.assertEqual(exc2, exc)
        else:
            self.fail("Exception should have been reraised")

    def test_install_scripts_soft_deps_incompatible_version(self):
        if IncompatibleVersionError is None:  # zc.buildout >= 1.7
            return  # @skip appears in py2.7

        exc = IncompatibleVersionError()
        try:
            self.do_test_install_scripts_soft_deps(exc=exc)
        except UserError as exc2:
            self.assertEqual(exc2, exc)
        else:
            self.fail("Exception should have been reraised")

    def test_install_scripts_soft_deps_user_error(self):
        self.do_test_install_scripts_soft_deps(
            exc=UserError("We don't have a distribution for "
                          "zztest-softreq==6.6.6\n"
                          "and can't install one in offline "
                          "(no-install) mode."))

    def test_install_scripts_soft_deps_user_error_reraise(self):
        exc = UserError("We don't have a distribution for "
                        "zztest-hardreq==6.6.6\n"
                        "and can't install one in offline "
                        "(no-install) mode.")

        try:
            self.do_test_install_scripts_soft_deps(exc=exc)
        except UserError as exc2:
            self.assertEqual(exc, exc2)
        else:
            self.fail("Expected the same UserError to be reraised")

    def test_install_scripts_70(self, with_devtools=True, **kw):
        kw['with_devtools'] = 'true' if with_devtools else 'false'
        self.make_recipe(version='local %s' % os.path.join(TEST_DIR, 'oerp70'),
                         gunicorn='direct',
                         **kw)
        self.recipe.version_detected = "7.0alpha"
        self.recipe.options['options.log_handler'] = ":INFO,werkzeug:WARNING"

        self.install_scripts(extra_develop={
            'openerp-command': 'fake_openerp-command'})

        expected = ['start_openerp',
                    'gunicorn_openerp',
                    'cron_worker_openerp']
        if with_devtools:
            expected.extend(('test_openerp', 'openerp_command'))
        self.assertScripts(expected)

    def test_install_scripts_70_no_devtools(self):
        self.test_install_scripts_70(with_devtools=False)

    def test_install_scripts_70_server_wide_modules(self):
        self.make_recipe(version='local %s' % os.path.join(TEST_DIR, 'oerp70'),
                         gunicorn='direct',
                         server_wide_modules='anybox_homepage')
        self.recipe.version_detected = "7.0alpha"
        self.recipe.options['options.log_handler'] = ":INFO,werkzeug:WARNING"

        self.install_scripts(extra_develop={
            'openerp-command': 'fake_openerp-command'})

        self.assertTrue("server_wide_modules=('web', 'anybox_homepage')"
                        in self.read_script('start_openerp'))
        with open(os.path.join(
                self.buildout_dir, 'etc', 'gunicorn_openerp.conf.py')) as gu:
            self.assertTrue(
                "openerp.conf.server_wide_modules = "
                "['web', 'anybox_homepage']\n"
                in gu)

    def test_install_scripts_80(self, with_devtools=True, **kw):
        kw['with_devtools'] = 'true' if with_devtools else 'false'
        self.make_recipe(version='local %s' % os.path.join(TEST_DIR, 'odoo80'),
                         gunicorn='direct', **kw)
        self.recipe.version_detected = "8.0alpha"
        self.recipe.options['options.log_handler'] = ":INFO,werkzeug:WARNING"

        self.install_scripts(extra_develop={
            'openerp-command': 'fake_openerp-command'})

        expected = ['start_openerp',
                    'gunicorn_openerp',
                    'cron_worker_openerp']
        if with_devtools:
            expected.extend(('test_openerp', 'openerp_command'))
        self.assertScripts(expected)

    def test_install_scripts_80_no_devtools(self):
        self.test_install_scripts_80(with_devtools='false')

    def test_install_scripts_70_gunicorn_proxied(self):
        self.make_recipe(version='local %s' % os.path.join(TEST_DIR, 'oerp70'),
                         gunicorn='proxied')
        self.recipe.version_detected = "7.0alpha"

        # necessary for openerp-command, will be part of post-release refactor
        self.recipe.options['options.addons_path'] = ''

        self.install_scripts(
            extra_develop={'openerp-command': 'fake_openerp-command'},
            setup_has_pil=True)
        self.assertScripts(('start_openerp',
                            'gunicorn_openerp',
                            'cron_worker_openerp',
                            ))

    def test_parse_openerp_scripts(self):
        self.make_recipe(
            version='local %s' % os.path.join(TEST_DIR, 'oerp70'),
            openerp_scripts=os.linesep.join((
                'myentry=script_name',
                'nosetests command-line-options=-d',
                'withargs=withargs arguments=session',
                'myentry=script_name_opt openerp-log-level=error '
                'command-line-options=-d,-f')),
        )

        self.recipe._parse_openerp_scripts()
        self.assertEqual(
            self.recipe.openerp_scripts,
            dict(script_name=dict(entry='myentry',
                                  command_line_options=[]),
                 withargs=dict(entry="withargs", arguments="session",
                               command_line_options=[]),
                 script_name_opt=dict(entry='myentry',
                                      openerp_log_level='ERROR',
                                      command_line_options=['-d', '-f']),
                 nosetests_openerp=dict(entry='nosetests',
                                        command_line_options=['-d'])))

    def test_parse_openerp_scripts_improper_log_level(self):
        self.make_recipe(
            version='local %s' % os.path.join(TEST_DIR, 'oerp70'),
            openerp_scripts=('myentry=script_name_opt openerp-log-level=cool '
                             'command-line-options=-d,-f'))
        self.assertRaises(UserError, self.recipe._parse_openerp_scripts)
