import os
import sys
import subprocess
from zc.buildout import UserError
from anybox.recipe.openerp.base import main_software
from ..testing import RecipeTestCase
from ..testing import get_vcs_log

TEST_DIR = os.path.dirname(__file__)


class TestBaseRecipe(RecipeTestCase):

    def get_source_type(self):
        return self.recipe.sources[main_software][0]

    def get_source_url(self):
        return self.recipe.sources[main_software][1]

    def assertDownloadUrl(self, url):
        """Assert that main software is 'downloadable' with given url."""
        source = self.recipe.sources[main_software]
        self.assertEquals(source[0], 'downloadable')
        self.assertEquals(source[1], url)

    def test_version_release_6_1(self):
        self.make_recipe(version='6.1-1')

        recipe = self.recipe
        self.assertEquals(recipe.version_wanted, '6.1-1')
        self.assertDownloadUrl(
            'http://nightly.odoo.com/old/openerp-6.1/blob-6.1-1.tgz')

    def test_version_nightly_6_1(self):
        self.make_recipe(version='nightly 6.1 1234-5')

        self.assertDownloadUrl(
            'http://nightly.odoo.com/6.1/nightly/src/'
            '6-1-nightly-1234-5.tbz')

    def test_version_bzr_6_1(self):
        self.make_recipe(
            version='bzr lp:openobject-server/6.1 openerp-6.1 last:1')

        recipe = self.recipe
        self.assertEquals(self.get_source_type(), 'bzr')
        self.assertEquals(self.get_source_url(),
                          ('lp:openobject-server/6.1', 'last:1'))
        self.assertEquals(recipe.openerp_dir,
                          os.path.join(recipe.parts, 'openerp-6.1'))

    def test_version_local(self):
        local_path = 'path/to/local/version'
        self.make_recipe(version='local ' + local_path)
        recipe = self.recipe
        self.assertEquals(self.get_source_type(), 'local')
        self.assertTrue(recipe.openerp_dir.endswith(local_path))

    def test_version_url(self):
        url = 'http://download.example/future/openerp-12.0.tgz'
        self.make_recipe(version='url ' + url)
        recipe = self.recipe
        self.assertDownloadUrl(url)
        self.assertEquals(recipe.archive_filename, 'openerp-12.0.tgz')

    def test_base_url(self):
        self.make_recipe(version='6.1-1',
                         base_url='http://example.org/openerp')
        self.assertDownloadUrl('http://example.org/openerp/blob-6.1-1.tgz')

    def test_base_url_nightly(self):
        self.make_recipe(version='nightly 6.1 1234-5',
                         base_url='http://example.org/openerp')
        self.assertDownloadUrl(
            'http://example.org/openerp/6-1-nightly-1234-5.tbz')

    def test_buildout_cfg_name(self):
        self.make_recipe(version='6.1-1')
        bcn = self.recipe.buildout_cfg_name
        self.assertEquals(bcn(), 'buildout.cfg')
        self.assertEquals(bcn(('-D', 'install', 'openerp')), 'buildout.cfg')
        self.assertEquals(bcn(('-c', '6.1.cfg')), '6.1.cfg')
        self.assertEquals(bcn(('--config', '6.1.cfg')), '6.1.cfg')
        self.assertEquals(bcn(('-o', '--config', '6.1.cfg')), '6.1.cfg')
        self.assertEquals(bcn(('--config=6.1.cfg',)), '6.1.cfg')
        self.assertEquals(bcn(('--config=6.1.cfg', '-o')), '6.1.cfg')

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
            """bzr lp:openerp-web web last:1 subdir=addons
               bzr lp:openobject-addons openerp-addons last:1
               # bzr lp:openerp-something/8.0 addons-something last:1""",
                ):
            self.assertRaises(UserError,
                              recipe.parse_addons, dict(addons=illformed))

    def develop_babel(self):
        """Develop fake babel in buildout's directory"""
        subprocess.check_call(
            [sys.executable,
             os.path.join(TEST_DIR, 'fake_babel', 'setup.py'),
             'develop',
             '-d', self.recipe.b_options['develop-eggs-directory'],
             '-b', os.path.join(self.buildout_dir, 'build')])

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
            version='git http://github.com/odoo/odoo.git odoo 7.0')
        self.recipe.version_detected = '7.0-somerev'
        oerp_dir = self.recipe.openerp_dir
        base_addons = os.path.join(oerp_dir, 'openerp', 'addons')
        odoo_addons = os.path.join(oerp_dir, 'addons')
        os.makedirs(base_addons)
        os.makedirs(odoo_addons)
        self.recipe.addons_paths = ['/some/separate/addons']
        self.recipe.finalize_addons_paths(check_existence=False)
        self.assertEquals(self.recipe.addons_paths,
                          [base_addons, odoo_addons, '/some/separate/addons'])

    def test_finalize_addons_paths_bzr_layout(self):
        self.make_recipe(
            version='bzr lp:openobject-server openerp last:1')
        self.recipe.version_detected = '7.0-somerev'
        oerp_dir = self.recipe.openerp_dir
        base_addons = os.path.join(oerp_dir, 'openerp', 'addons')
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
            version='git http://github.com/odoo/odoo.git odoo 7.0')
        self.recipe.version_detected = '7.0-somerev'
        oerp_dir = self.recipe.openerp_dir
        base_addons = os.path.join(oerp_dir, 'openerp', 'addons')
        odoo_addons = os.path.join(oerp_dir, 'addons')
        os.makedirs(base_addons)
        os.makedirs(odoo_addons)
        self.recipe.addons_paths = ['/some/separate/addons',
                                    odoo_addons]
        self.recipe.finalize_addons_paths(check_existence=False)
        self.assertEquals(self.recipe.addons_paths,
                          [base_addons, '/some/separate/addons', odoo_addons])

    def test_finalize_addons_paths_60_layout(self):
        self.make_recipe(version='6.0.4')
        recipe = self.recipe
        recipe.version_detected = '6.0.4'
        oerp_dir = recipe.openerp_dir = os.path.join(recipe.parts, 'oerp60')
        base_addons = os.path.join(oerp_dir, 'bin', 'addons')
        os.makedirs(base_addons)
        recipe.addons_paths = ['/some/separate/addons']
        recipe.finalize_addons_paths(check_existence=False)
        self.assertEquals(self.recipe.addons_paths, [base_addons,
                                                     '/some/separate/addons'])
