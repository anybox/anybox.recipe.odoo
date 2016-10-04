import os
import sys
from copy import deepcopy

from zc.buildout import UserError
from ..server import BaseRecipe
from ..base import main_software
from ..base import WITH_ODOO_REQUIREMENTS_FILE_OPTION
from ..testing import RecipeTestCase
from ..testing import get_vcs_log

TEST_DIR = os.path.dirname(__file__)


class TestingRecipe(BaseRecipe):
    """A subclass with just enough few defaults for unit testing."""

    release_filenames = {'10.0': 'blob-%s.tgz'}
    nightly_filenames = {'10.0rc1c': '10.0%s.tar.gz'}
    release_dl_url = {'10.0': 'http://release.odoo.test/src/'}


class TestBaseRecipe(RecipeTestCase):

    def setUp(self):
        super(TestBaseRecipe, self).setUp()
        self.test_dir = TEST_DIR

    def get_source_type(self):
        return self.recipe.sources[main_software][0]

    def get_source_url(self):
        return self.recipe.sources[main_software][1]

    def assertDownloadUrl(self, url):
        """Assert that main software is 'downloadable' with given url."""
        source = self.recipe.sources[main_software]
        self.assertEquals(source[0], 'downloadable')
        self.assertEquals(source[1], url)

    def test_version_release_10_0(self):
        self.make_recipe(version='10.0')

        recipe = self.recipe
        self.assertEquals(recipe.version_wanted, '10.0')
        self.assertDownloadUrl('http://release.odoo.test/src/blob-10.0.tgz')

    def test_version_nightly_10_0(self):
        self.make_recipe(version='nightly 10.0rc1c latest')

        self.assertDownloadUrl(
            'http://nightly.odoo.com/10.0/nightly/src/10-0-nightly-latest.tbz')

    def test_version_local(self):
        local_path = 'path/to/local/version'
        self.make_recipe(version='local ' + local_path)
        recipe = self.recipe
        self.assertEquals(self.get_source_type(), 'local')
        self.assertTrue(recipe.odoo_dir.endswith(local_path))

    def test_version_url(self):
        url = 'http://download.example/future/odoo-12.0.tgz'
        self.make_recipe(version='url ' + url)
        recipe = self.recipe
        self.assertDownloadUrl(url)
        self.assertEquals(recipe.archive_filename, 'odoo-12.0.tgz')

    def test_base_url(self):
        self.make_recipe(version='10.0-1',
                         base_url='http://example.org/odoo')
        self.assertDownloadUrl('http://example.org/odoo/blob-10.0-1.tgz')

    def test_base_url_nightly(self):
        self.make_recipe(version='nightly 10.0rc1c latest',
                         base_url='http://example.org/odoo')
        self.assertDownloadUrl(
            'http://example.org/odoo/10-0-nightly-latest.tbz')

    def test_buildout_cfg_name(self):
        self.make_recipe(version='10.0-1')
        bcn = self.recipe.buildout_cfg_name
        self.assertEquals(bcn(), 'buildout.cfg')
        self.assertEquals(bcn(('-D', 'install', 'odoo')), 'buildout.cfg')
        self.assertEquals(bcn(('-c', '10.0.cfg')), '10.0.cfg')
        self.assertEquals(bcn(('--config', '10.0.cfg')), '10.0.cfg')
        self.assertEquals(bcn(('-o', '--config', '10.0.cfg')), '10.0.cfg')
        self.assertEquals(bcn(('--config=10.0.cfg',)), '10.0.cfg')
        self.assertEquals(bcn(('--config=10.0.cfg', '-o')), '10.0.cfg')

    def test_parse_addons_revisions(self):
        """Test both parse_addons and parse_revisions."""
        self.make_recipe(version='bzr lp:openobject-server server last:1'
                         ' option=option')
        recipe = self.recipe

        recipe.parse_revisions(dict(revisions='1234'))
        self.assertEquals(recipe.sources[main_software],
                          ('bzr', ('lp:openobject-server', '1234'),
                           dict(option='option')))

        recipe.parse_addons(
            dict(addons='hg http://some/repo addons-specific default opt=spam')
        )
        self.assertEquals(recipe.sources['addons-specific'],
                          ('hg', ('http://some/repo', 'default'),
                           {'opt': 'spam'}))

        recipe.parse_revisions(dict(revisions='1111\naddons-specific 1.0'))
        self.assertEquals(recipe.sources['addons-specific'],
                          ('hg', ('http://some/repo', '1.0'), {'opt': 'spam'}))
        self.assertEquals(recipe.sources[main_software][1][1], '1111')

        # with a comment
        recipe.parse_revisions(dict(revisions='1112 ; main software'
                                    '\naddons-specific 1.0'))
        self.assertEquals(recipe.sources[main_software][1][1], '1112')

    def test_parse_addons_illformed(self):
        """Test that common mistakes end up as UserError."""
        self.make_recipe(version='bzr lp:openobject-server server last:1'
                         ' option=option')
        recipe = self.recipe

        for illformed in (
            # bad option
            'hg http://some/repo addons-specific default opt:spam',
            # attempt to comment a line
            """bzr lp:odoo-web web last:1 subdir=addons
               bzr lp:openobject-addons odoo-addons last:1
               # bzr lp:odoo-something/10.0 addons-something last:1""",
                ):
            self.assertRaises(UserError,
                              recipe.parse_addons, dict(addons=illformed))

    def test_clean(self):
        """Test clean for local server & addons and base class vcs addons.
        """
        self.make_recipe(
            version='local server-dir',
            addons=os.linesep.join((
                'local addon-dir',
                'fakevcs http://some/repo vcs-addons revspec')),
            clean='true')

        b_dir = self.recipe.buildout_dir
        for d in (['server-dir'], ['server-dir', 'a'],
                  ['addon-dir'],
                  ['addon-dir', 'a'], ['addon-dir', 'b'],
                  ['vcs-addons'],
                  ['vcs-addons', 'a']):
            os.mkdir(os.path.join(b_dir, *d))
        for path in (['server-dir', 'a', 'x.pyc'],
                     ['addon-dir', 'a', 'x.pyc'],
                     ['addon-dir', 'b', 'x.pyo'],
                     ['addon-dir', 'b', 'other-file'],
                     ['vcs-addons', 'a', 'x.pyc'],
                     ['vcs-addons', 'a', 'x.py'],
                     ):
            with open(os.path.join(b_dir, *path), 'w') as f:
                f.write("content")
        self.recipe.retrieve_main_software()
        self.recipe.retrieve_addons()

        for path, expected in (
                (('server-dir',), True),
                (('server-dir', 'a', 'x.pyc'), False),
                (('server-dir', 'a'), False),
                (('vcs-addons', 'a', 'x.py'), True),
                (('vcs-addons', 'a', 'x.pyc'), False),
                (('addon-dir',), True),
                (('addon-dir', 'a', 'x.pyc'), False),
                (('addon-dir', 'a'), False),
                (('addon-dir', 'b'), True),
                (('addon-dir', 'b', 'x.pyo'), False),
                (('addon-dir', 'b', 'other-file'), True)):
            self.assertEquals(os.path.exists(os.path.join(b_dir, *path)),
                              expected)

    def test_clean_vcs_server(self):
        """Test clean for base class vcs server."""
        self.make_recipe(
            version='fakevcs http://some/where server-dir somerev',
            clean='true')

        b_dir = self.recipe.buildout_dir
        server_path = os.path.join(b_dir, 'parts', 'server-dir')
        os.makedirs(os.path.join(server_path, 'a'))
        for path in (['a', 'x.pyc'],
                     ['a', 'x.py'],
                     ):
            with open(os.path.join(server_path, *path), 'w') as f:
                f.write("content")
        self.recipe.retrieve_main_software()
        self.recipe.retrieve_addons()

        for path, expected in (
                (('a',), True),
                (('a', 'x.pyc'), False),
                (('a', 'x.py'), True)):
            self.assertEquals(os.path.exists(os.path.join(server_path, *path)),
                              expected)

    def path_from_buildout(self, *relpath, **opt):
        relpath = list(relpath)
        if opt.get('from_parts'):
            relpath.insert(0, self.recipe.parts)
        return self.recipe.make_absolute(os.path.join(*relpath))

    def test_vcs_revert(self):
        """Test clean forwarding to vcs impl."""
        self.make_recipe(
            version='fakevcs http://some/where server-dir mainrev')
        self.recipe.revert_sources()
        self.assertEqual(get_vcs_log(), [
            ('revert', 'mainrev',
             self.path_from_buildout('server-dir', from_parts=True))])

    def test_vcs_revert_standalone(self):
        """Test clean forwarding to vcs impl, taking group path into acount"""
        self.make_recipe(
            version='local server-dir',
            addons='fakevcs http://some/where adddir addrev group=spam')
        self.recipe.revert_sources()
        self.assertEqual(get_vcs_log(), [
            ('revert', 'addrev', self.path_from_buildout('spam', 'adddir'))])

    def test_vcs_revert_not_implemented(self):
        """Revert must not fail if a repo does not implement it."""
        self.make_recipe(
            version='fakevcs http://some/where server-dir mainrev')
        from ..testing import FakeRepo
        orig_revert = FakeRepo.revert

        def notimp_revert(self, rev):
            raise NotImplementedError

        FakeRepo.revert = notimp_revert
        try:
            self.recipe.revert_sources()
        finally:
            FakeRepo.revert = orig_revert

        self.assertEqual(get_vcs_log(), [])

    def test_finalize_addons_paths_git_layout(self):
        self.make_recipe(
            version='git http://github.com/odoo/odoo.git odoo 10.0')
        self.recipe.version_detected = '10.0-somerev'
        oerp_dir = self.recipe.odoo_dir
        base_addons = os.path.join(oerp_dir, 'odoo', 'addons')
        odoo_addons = os.path.join(oerp_dir, 'addons')
        os.makedirs(base_addons)
        os.makedirs(odoo_addons)
        self.recipe.addons_paths = ['/some/separate/addons']
        self.recipe.finalize_addons_paths(check_existence=False)
        self.assertEquals(self.recipe.addons_paths,
                          [base_addons, odoo_addons, '/some/separate/addons'])

    def test_finalize_addons_paths_bzr_layout(self):
        self.make_recipe(
            version='bzr lp:openobject-server odoo last:1')
        self.recipe.version_detected = '10.0-somerev'
        oerp_dir = self.recipe.odoo_dir
        base_addons = os.path.join(oerp_dir, 'odoo', 'addons')
        os.makedirs(base_addons)
        self.recipe.addons_paths = ['/some/separate/addons']
        self.recipe.finalize_addons_paths(check_existence=False)
        self.assertEquals(self.recipe.addons_paths, [base_addons,
                                                     '/some/separate/addons'])

    def test_finalize_addons_paths_order(self):
        """Test finalize_addons_paths keeps addons_path order
        Ensure we don't move odoo addons in addons_path if it has been
        set as local
        """
        self.make_recipe(
            version='git http://github.com/odoo/odoo.git odoo 10.0')
        self.recipe.version_detected = '10.0-somerev'
        oerp_dir = self.recipe.odoo_dir
        base_addons = os.path.join(oerp_dir, 'odoo', 'addons')
        odoo_addons = os.path.join(oerp_dir, 'addons')
        os.makedirs(base_addons)
        os.makedirs(odoo_addons)
        self.recipe.addons_paths = ['/some/separate/addons',
                                    odoo_addons]
        self.recipe.finalize_addons_paths(check_existence=False)
        self.assertEquals(self.recipe.addons_paths,
                          [base_addons, '/some/separate/addons', odoo_addons])

    def make_recipe_appplying_requirements_file(self, reqs_content):
        """Prepare recipe object and requirements file

        :param reqs_content: if ``None`` the file is not created at all
        """
        opts = {}
        opts[WITH_ODOO_REQUIREMENTS_FILE_OPTION] = 'true'
        self.make_recipe(
            version='git http://github.com/odoo/odoo.git odoo 10.0', **opts)

        self.recipe.version_detected = '10.0-somerev'
        oerp_dir = self.recipe.odoo_dir
        os.makedirs(oerp_dir)
        if reqs_content is None:
            return

        with open(os.path.join(self.recipe.odoo_dir,
                               'requirements.txt'), 'w') as f:
            f.write(reqs_content + '\n')

    def apply_requirements_file(self, pre_versions=None):
        """Call the recipe method, instrospects and return versions as a dict.

        :param dict pre_versions: if supplied, will be set before calling the
                                  recipe's code
        """
        import pip as pip_original
        from zc.buildout.easy_install import Installer
        versions_original = deepcopy(Installer._versions)

        versions = Installer._versions
        if pre_versions is not None:
            versions.update(pre_versions)
        try:
            self.recipe.apply_odoo_requirements_file()
        finally:
            sys.modules['pip'] = pip_original
            Installer._versions = versions_original

        return versions

    def test_apply_requirements_file(self):
        """Unit test for Odoo requirements.txt passing to internals
        """
        dist_name = 'someproject'
        self.make_recipe_appplying_requirements_file("%s==1.2.3" % dist_name)
        versions = self.apply_requirements_file()

        self.assertEqual(versions.get(dist_name), '1.2.3')
        self.assertTrue(dist_name in self.recipe.requirements,
                        msg="Egg %r should have been listed" % dist_name)

    def test_apply_requirements_file_no_reqfile(self):
        """Unit test for Odoo requirements.txt: if the file is missing
        """
        dist_name = 'someproject'
        self.make_recipe_appplying_requirements_file(None)
        versions = self.apply_requirements_file()

        self.assertFalse(dist_name in versions)
        self.assertFalse(dist_name in self.recipe.requirements)

    def test_apply_requirements_file_no_version(self):
        """Unit test for Odoo requirements.txt: corner case with no version
        """
        dist_name = 'someprojectzz'
        self.make_recipe_appplying_requirements_file(dist_name)
        versions = self.apply_requirements_file()

        self.assertFalse(dist_name in versions)
        self.assertTrue(dist_name in self.recipe.requirements,
                        msg="Egg %r should have been listed" % dist_name)

    def test_apply_requirements_file_precedence1(self):
        """Unit test for Odoo requirements.txt: [versions] should win

        The setting of version in the test is actually lower level, close to
        the tested code logic, so that we are close to tautology. Anyway, this
        gets at least the tested code executed.
        """
        dist_name = 'someproject'
        self.make_recipe_appplying_requirements_file("%s==1.2.3" % dist_name)
        versions = self.apply_requirements_file(
            pre_versions={dist_name: '17.2'})
        self.assertEqual(versions.get(dist_name), '17.2')

    def test_list_develops(self):
        self.make_recipe(
            version='git http://github.com/odoo/odoo.git odoo 10.0')
        self.assertEqual(self.recipe.list_develops(), [])
        self.develop_fictive()
        self.assertEqual(self.recipe.list_develops(),
                         [self.fictive_dist_name])

    def test_apply_requirements_file_precedence2(self):
        """Unit test for Odoo requirements.txt: develops should win
        """
        self.make_recipe_appplying_requirements_file(
            self.fictive_dist_name + "==6.2.3")
        self.develop_fictive()
        versions = self.apply_requirements_file()
        self.assertFalse(self.fictive_dist_name in versions)

    def test_apply_requirements_file_unsupported(self):
        """Unit test for Odoo requirements.txt: error paths #1
        """
        self.make_recipe_appplying_requirements_file("foo>=1.2.3")
        self.assertRaises(UserError, self.apply_requirements_file)

    def test_apply_requirements_file_unsupported2(self):
        """Unit test for Odoo requirements.txt: error paths #2
        """
        self.make_recipe_appplying_requirements_file("spam==1.2.3, >2.0")
        self.assertRaises(UserError, self.apply_requirements_file)
