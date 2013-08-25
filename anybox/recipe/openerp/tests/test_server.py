"""Test the server recipe.

NB: zc.buildout.testing provides utilities for integration tests, with
an embedded http server, etc.
"""
import os
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
        self.assertRaises(ValueError, self.recipe.retrieve_addons)

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

    def check_retrieve_addons_single(self, dirname):
        """The VCS is a whole addon."""
        self.make_recipe(version='6.1',
                         addons='fakevcs custom %s last:1' % dirname)
        dirname = dirname.rstrip('/')
        # manual creation of our single addon
        addon_dir = os.path.join(self.buildout_dir, dirname)
        os.mkdir(addon_dir)
        open(os.path.join(addon_dir, '__openerp__.py'), 'w').close()

        self.recipe.retrieve_addons()
        paths = self.recipe.addons_paths
        self.assertEquals(paths, [addon_dir])
        self.assertEquals(os.listdir(addon_dir), [dirname])
        moved_addon = os.path.join(addon_dir, dirname)
        self.assertTrue('__openerp__.py' in os.listdir(moved_addon))

        # update works
        self.recipe.retrieve_addons()
        self.assertEquals(get_vcs_log()[-1][0], moved_addon)

    def test_retrieve_addons_single(self):
        """The VCS is a whole addon."""
        self.check_retrieve_addons_single('addon')

    def test_retrieve_addons_single_trailing_slash(self):
        """The VCS is a whole addon, its target directory has a trailing /"""
        self.check_retrieve_addons_single('addon/')

    def test_retrieve_addons_single_collision(self):
        """The VCS is a whole addon, and there's a collision in renaming"""
        self.make_recipe(version='6.1', addons='fakevcs custom addon last:1')
        addon_dir = os.path.join(self.buildout_dir, 'addon')
        os.mkdir(addon_dir)
        open(os.path.join(addon_dir, '__openerp__.py'), 'w').close()

        self.recipe.retrieve_addons()
        paths = self.recipe.addons_paths
        self.assertEquals(paths, [addon_dir])
        self.assertEquals(os.listdir(addon_dir), ['addon'])
        self.assertTrue(
            '__openerp__.py' in os.listdir(os.path.join(addon_dir, 'addon')))

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
            if not script in binlist:
                self.fail("Script %r missing in bin directory." % script)

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
        self.assertEquals(paths, [addons_dir,
                                  os.path.join(oerp_dir, 'openerp', 'addons')])

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
        self.assertEqual(paths, [addons_dir, root_dir])
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

    def test_install_scripts_soft_deps(self):
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
        self.unreachable_distributions.add(softreq)

        self.install_scripts(extra_requirements=(softreq,))
        self.assertScripts(('start_openerp',
                            'test_openerp',
                            'gunicorn_openerp',
                            'cron_worker_openerp',
                            ))

    def test_install_scripts_70(self):
        self.make_recipe(version='local %s' % os.path.join(TEST_DIR, 'oerp70'),
                         gunicorn='direct',
                         with_devtools='true')
        self.recipe.version_detected = "7.0alpha"
        self.recipe.options['options.log_handler'] = ":INFO,werkzeug:WARNING"

        self.install_scripts(extra_develop={
            'openerp-command': 'fake_openerp-command'})
        self.assertScripts(('start_openerp',
                            'test_openerp',
                            'gunicorn_openerp',
                            'cron_worker_openerp',
                            'openerp_command',
                            ))

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
                'myentry=script_name_opt command-line-options=-d,-f')),
        )

        self.recipe._parse_openerp_scripts()
        self.assertEqual(
            self.recipe.openerp_scripts,
            dict(script_name=dict(entry='myentry',
                                  command_line_options=[]),
                 withargs=dict(entry="withargs", arguments="session",
                               command_line_options=[]),
                 script_name_opt=dict(entry='myentry',
                                      command_line_options=['-d', '-f']),
                 nosetests_openerp=dict(entry='nosetests',
                                        command_line_options=['-d'])))
