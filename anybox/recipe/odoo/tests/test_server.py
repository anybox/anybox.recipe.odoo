"""Test the server recipe.

NB: zc.buildout.testing provides utilities for integration tests, with
an embedded http server, etc.
"""
import os
from pkg_resources import Requirement

from ..base import MissingDistribution
from ..base import IncompatibleConstraintError
from zc.buildout import UserError
from ..server import ServerRecipe
from ..testing import get_vcs_log
from ..testing import RecipeTestCase

TEST_DIR = os.path.dirname(__file__)


class TestingRecipe(ServerRecipe):
    """A subclass helping with the fact that there are no Odoo releases.

    This is merely to avoid rewriting many tests.
    """
    release_filenames = {'10.0': 'fake-release-%s.tgz'}
    release_dl_url = {'10.0': 'http://release.odoo.test/src/'}


class TestServer(RecipeTestCase):

    def make_recipe(self, name='odoo', **options):
        self.recipe = TestingRecipe(self.buildout, name, options)

    def test_retrieve_addons_local(self):
        """Setting up a local addons line."""
        addons_dir = os.path.join(self.buildout_dir, 'addons-custom')
        self.make_recipe(version='10.0', addons='local addons-custom')

        self.recipe.retrieve_addons()
        paths = self.recipe.addons_paths
        self.assertEquals(get_vcs_log(), [])
        self.assertEquals(paths, [addons_dir])

    def test_retrieve_addons_local_standalone(self):
        """A local standalone addon is  permitted."""
        addons_dir = os.path.join(self.buildout_dir, 'addons-custom')
        os.mkdir(addons_dir)
        with open(os.path.join(addons_dir, '__manifest__.py'), 'w') as f:
            f.write("#Empty python package")
        self.make_recipe(version='10.0', addons='local addons-custom')
        print(self.recipe.retrieve_addons)
        self.assertTrue(self.recipe.retrieve_addons)

    def test_retrieve_addons_local_options(self):
        """Addons options work for 'local' by testing (useless) subdir option.
        """
        custom_dir = os.path.join(self.buildout_dir, 'custom')
        addons_dir = os.path.join(custom_dir, 'addons')
        self.make_recipe(version='10.0', addons='local custom subdir=addons')

        self.recipe.retrieve_addons()
        paths = self.recipe.addons_paths
        self.assertEquals(get_vcs_log(), [])
        self.assertEquals(paths, [addons_dir])

    def test_retrieve_addons_vcs(self):
        """A VCS line in addons."""
        self.make_recipe(version='10.0', addons='fakevcs http://trunk.example '
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
        self.make_recipe(version='10.0', addons=os.linesep.join((
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
            version='10.0',
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
        self.make_recipe(version='10.0', addons='fakevcs lp:odoo-web web '
                         'last:1 subdir=addons bzrinit=branch')
        # manual creation because fakevcs does nothing but retrieve_addons
        # has assertions on existence of target directories
        web_dir = os.path.join(self.buildout_dir, 'web')
        web_addons_dir = os.path.join(web_dir, 'addons')

        self.recipe.retrieve_addons()
        paths = self.recipe.addons_paths
        self.assertEquals(get_vcs_log(), [
                          (web_dir, 'lp:odoo-web', 'last:1',
                           dict(offline=False, clear_locks=False, clean=False,
                                    subdir="addons", bzrinit="branch"))
                          ])
        self.assertEquals(paths, [web_addons_dir])

    def test_retrieve_addons_standalone_grouped(self):
        self.make_recipe(
            version='10.0',
            addons='fakevcs lp:my-addons1 addons1 '
                    'last:1 group=grouped\nfakevcs lp:my-addons2 addons2 '
                    'last:1 group=grouped'
        )
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
        """Standalone addons could be  declared by the 'group' option."""
        dirname = 'standalone'
        self.make_recipe(version='10.0',
                         addons='group custom %s last:1' % dirname)
        dirname = dirname.rstrip('/')

        # manual creation of our single addon
        addon_dir = os.path.join(self.buildout_dir, dirname)
        os.mkdir(addon_dir)
        open(os.path.join(addon_dir, '__manifest__.py'), 'w').close()
        print(self.recipe.retrieve_addons)
        self.assertTrue(self.recipe.retrieve_addons)

    def test_retrieve_addons_clear_locks(self):
        """Retrieving addons with vcs-clear-locks option."""
        addons_dir = os.path.join(self.buildout_dir, 'addons')
        options = dict(version='10.0', addons='fakevcs lp:my-addons addons -1')
        options['vcs-clear-locks'] = 'True'
        self.make_recipe(**options)
        self.recipe.retrieve_addons()
        self.assertEquals(get_vcs_log(), [
                          (addons_dir, 'lp:my-addons', '-1',
                           dict(offline=False, clear_locks=True, clean=False))
                          ])

    def test_merge_requirements(self):
        self.make_recipe(version='10.0')
        self.recipe.version_detected = '10.0-1'
        self.recipe.merge_requirements()
        self.assertEquals(set(self.recipe.requirements),
                          set(['anybox.recipe.odoo',
                               'odoo']))

    def test_merge_requirements_new_project_name(self):
        """At any point in time, Odoo is prone to change package name."""
        self.make_recipe(version='local %s' % os.path.join(
            TEST_DIR, 'odoo-project-renaming'))
        self.recipe.version_detected = '10.0'
        self.recipe.merge_requirements()
        self.assertEquals(set(self.recipe.requirements),
                          set(['anybox.recipe.odoo',
                               'odoo']))

    def test_merge_requirements_gunicorn(self):
        self.make_recipe(version='10.0', gunicorn='direct')
        self.recipe.version_detected = '10.0-1'
        self.recipe.apply_version_dependent_decisions()  # TODO make a helper
        self.recipe.merge_requirements()
        req = self.recipe.requirements
        self.assertTrue('gunicorn' in req)
        self.assertTrue('psutil' in req)

    def test_merge_requirements_devtools(self):
        self.make_recipe(version='10.0', with_devtools='true')
        self.recipe.version_detected = '10.0-1'
        self.recipe.merge_requirements()
        from .. import devtools
        self.assertTrue(set(devtools.requirements).issubset(
            self.recipe.requirements))

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

    def test_retrieve_fixup_addons_check(self):
        """Test that existence check of addons paths is done."""
        oerp_dir = os.path.join(TEST_DIR, 'odoo10')
        self.make_recipe(version='local %s' % oerp_dir,
                         addons='local addons-custom',
                         )

        self.recipe.version_detected = "10.0.0"
        self.recipe.retrieve_addons()
        self.assertRaises(AssertionError, self.recipe.finalize_addons_paths)

    def test_forbid_addons_paths_option(self):
        oerp_dir = os.path.join(TEST_DIR, 'odoo10')
        self.make_recipe(version='local %s' % oerp_dir,
                         addons='local addons-custom',
                         )
        self.recipe.options['options.addons_path'] = '/tmp/some/addon'
        self.recipe.version_detected = "6.0.4"
        self.assertRaises(UserError, self.recipe.finalize_addons_paths,
                          check_existence=False)

    def install_scripts(self, extra_develop=None,
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
        self.recipe.develop(self.recipe.odoo_dir)

        bindir = os.path.join(self.buildout_dir, 'bin')
        os.mkdir(bindir)

        self.recipe._register_extra_paths()
        self.recipe._install_startup_scripts()

    def do_test_install_scripts_soft_deps(self, exc=None):
        """If a soft requirement is missing, the scripts are still generated.
        """
        self.make_recipe(version='local %s' % os.path.join(TEST_DIR, 'odoo10'),
                         gunicorn='direct',
                         with_devtools='true')
        self.recipe.version_detected = "10.0-20121003-233130"

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
        self.assertScripts(('start_odoo',
                            'test_odoo',
                            'gunicorn_odoo',
                            'cron_worker_odoo',
                            ))

    def test_install_scripts_indirect_soft_deps(self, exc=None):
        """If a requirement is soft and indirect, UserError is properly raised.
        """
        self.make_recipe(version='local %s' % os.path.join(TEST_DIR, 'odoo10'),
                         gunicorn='direct',
                         with_devtools='true')
        self.recipe.version_detected = "10.0"

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
        req = Requirement.parse("zztest-softreq==1.2.3")
        self.do_test_install_scripts_soft_deps(
            exc=IncompatibleConstraintError('Bad constraint', '>2', req))

    def test_install_scripts_soft_deps_incompatible_constraint_reraise(self):
        req = Requirement.parse("zztest-hardreq==1.2.3")
        exc = IncompatibleConstraintError('Bad constraint', '>2', req)
        try:
            self.do_test_install_scripts_soft_deps(exc=exc)
        except IncompatibleConstraintError as exc2:
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

    def test_install_scripts_10(self, with_devtools=True, **kw):
        kw['with_devtools'] = 'true' if with_devtools else 'false'
        self.make_recipe(version='local %s' % os.path.join(TEST_DIR, 'odoo10'),
                         gunicorn='direct', **kw)
        self.recipe.version_detected = "10.0alpha"
        self.recipe.options['options.log_handler'] = ":INFO,werkzeug:WARNING"

        self.install_scripts()

        expected = ['start_odoo',
                    'gunicorn_odoo',
                    'cron_worker_odoo']
        if with_devtools:
            expected.append('test_odoo')
        self.assertScripts(expected)

    def test_install_scripts_10_no_devtools(self):
        self.test_install_scripts_10(with_devtools=False)

    def test_gunicorn_preload_databases(self, databases='onedb',
                                        expected="('onedb',)"):
        self.make_recipe(version='local %s' % os.path.join(TEST_DIR, 'odoo10'),
                         gunicorn='direct')
        self.recipe.version_detected = "7.0"
        self.recipe.options['gunicorn.preload_databases'] = databases
        self.recipe.options['options.log_handler'] = ":INFO,werkzeug:WARNING"

        self.install_scripts()

        self.assertScripts(['gunicorn_odoo'])
        gunicorn_conf = os.path.join(self.recipe.etc,
                                     'gunicorn_odoo.conf.py')
        self.assertTrue(os.path.exists(gunicorn_conf))
        with open(gunicorn_conf) as conf:
            for line in conf:
                if 'preload_dbs =' in line:
                    self.assertEqual(line.strip(), "preload_dbs = " + expected)

    def test_gunicorn_preload_databases_multiple(self):
        self.test_gunicorn_preload_databases(databases='db1\ndb2',
                                             expected="('db1', 'db2')")

    def test_install_scripts_10_server_wide_modules(self):
        self.make_recipe(version='local %s' % os.path.join(TEST_DIR, 'odoo10'),
                         gunicorn='direct',
                         server_wide_modules='anybox_homepage')
        self.recipe.version_detected = "10.0alpha"
        self.recipe.options['options.log_handler'] = ":INFO,werkzeug:WARNING"

        self.install_scripts()

        self.assertTrue("server_wide_modules=('web', 'anybox_homepage')"
                        in self.read_script('start_odoo'))
        with open(os.path.join(
                self.buildout_dir, 'etc', 'gunicorn_odoo.conf.py')) as gu:
            self.assertTrue(
                "odoo.conf.server_wide_modules = "
                "['web', 'anybox_homepage']\n"
                in gu)

    def test_install_scripts_10_gunicorn_proxied(self):
        self.make_recipe(version='local %s' % os.path.join(TEST_DIR, 'odoo10'),
                         gunicorn='proxied')
        self.recipe.version_detected = "10.0alpha"

        self.install_scripts()
        self.assertScripts(('start_odoo',
                            'gunicorn_odoo',
                            'cron_worker_odoo',
                            ))

    def test_parse_odoo_scripts(self):
        self.make_recipe(
            version='local %s' % os.path.join(TEST_DIR, 'odoo10'),
            odoo_scripts=os.linesep.join((
                'myentry=script_name',
                'nosetests command-line-options=-d',
                'withargs=withargs arguments=session',
                'myentry=script_name_opt odoo-log-level=ERROR '
                'command-line-options=-d,-f')),
        )
        self.recipe._parse_odoo_scripts()
        self.assertEqual(
            self.recipe.odoo_scripts,
            dict(
                script_name=dict(
                    entry='myentry', command_line_options=[]
                ),
                withargs=dict(
                     entry="withargs", arguments="session",
                     command_line_options=[]
                ),
                script_name_opt=dict(
                     entry='myentry', odoo_log_level='ERROR',
                     command_line_options=['-d', '-f']
                ),
                nosetests_odoo=dict(
                     entry='nosetests', command_line_options=['-d'])
            )
        )

    def test_parse_odoo_scripts_improper_log_level(self):
        self.make_recipe(
            version='local %s' % os.path.join(TEST_DIR, 'odoo10'),
            odoo_scripts=(
                'myentry=script_name_opt odoo-log-level=cool '
                'command-line-options=-d,-f'
            )
        )
        self.assertRaises(UserError, self.recipe._parse_odoo_scripts)
