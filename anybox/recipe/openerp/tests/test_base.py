import os
import sys
import subprocess
import shutil
import tempfile
from ConfigParser import ConfigParser, NoOptionError
from anybox.recipe.openerp.server import BaseRecipe
from anybox.recipe.openerp.base import main_software
from anybox.recipe.openerp.base import GP_VCS_EXTEND_DEVELOP
from anybox.recipe.openerp.testing import RecipeTestCase
from ..testing import COMMIT_USER_FULL

TEST_DIR = os.path.dirname(__file__)


class TestingRecipe(BaseRecipe):
    """A subclass with just enough few defaults for unit testing."""

    archive_filenames = {'6.1': 'blob-%s.tgz'}
    archive_nightly_filenames = {'6.1': '6-1-nightly-%s.tbz'}


class TestBaseRecipe(RecipeTestCase):

    def make_recipe(self, name='openerp', **options):
        self.recipe = TestingRecipe(self.buildout, name, options)

    def get_source_type(self):
        return self.recipe.sources[main_software][0]

    def get_source_url(self):
        return self.recipe.sources[main_software][1][0]

    def assertDownloadUrl(self, url):
        """Assert that main software is 'downloadable' with given url."""
        source = self.recipe.sources[main_software]
        self.assertEquals(source[0], 'downloadable')
        self.assertEquals(source[1][0], url)

    def test_version_release_6_1(self):
        self.make_recipe(version='6.1-1')

        recipe = self.recipe
        self.assertEquals(recipe.version_wanted, '6.1-1')
        self.assertDownloadUrl(
            'http://nightly.openerp.com/6.1/releases/blob-6.1-1.tgz')

    def test_version_nightly_6_1(self):
        self.make_recipe(version='nightly 6.1 1234-5')

        self.assertDownloadUrl(
            'http://nightly.openerp.com/6.1/nightly/src/'
            '6-1-nightly-1234-5.tbz')

    def test_version_bzr_6_1(self):
        self.make_recipe(
            version='bzr lp:openobject-server/6.1 openerp-6.1 last:1')

        recipe = self.recipe
        self.assertEquals(self.get_source_type(), 'bzr')
        self.assertEquals(self.get_source_url(), 'lp:openobject-server/6.1')
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

    def build_babel_egg(self):
        """build an egg for fake babel in buildout's eggs directory."""
        subprocess.check_call(
            [sys.executable,
             os.path.join(TEST_DIR, 'fake_babel', 'setup.py'),
             'bdist_egg',
             '-d', self.recipe.b_options['eggs-directory'],
             '-b', os.path.join(self.buildout_dir, 'build')])

    def develop_babel(self):
        """Develop fake babel in buildout's directory"""
        subprocess.check_call(
            [sys.executable,
             os.path.join(TEST_DIR, 'fake_babel', 'setup.py'),
             'develop',
             '-d', self.recipe.b_options['develop-eggs-directory'],
             '-b', os.path.join(self.buildout_dir, 'build')])

    def test_freeze_egg_versions(self):
        """Test that an egg requirement is properly dumped with its version.
        """
        conf = ConfigParser()
        conf.add_section('freeze')
        self.make_recipe(version='6.1-1')
        self.build_babel_egg()
        self.recipe.options['eggs'] = 'Babel'
        self.recipe.install_requirements()  # to get 'ws' attribute
        self.recipe._freeze_egg_versions(conf, 'freeze')
        try:
            version = conf.get('freeze', 'Babel')
        except NoOptionError:
            self.fail("Expected version of Babel egg not dumped !")
        self.assertEquals(version, '0.123')

    def test_freeze_egg_versions_merge(self):
        """Test that freezing of egg versions keeps eggs already dumped.

        very much similar to test_freeze_egg_versions.
        """
        conf = ConfigParser()
        conf.add_section('freeze')
        conf.set('freeze', 'some.distribution', '1.0alpha')
        self.make_recipe(version='6.1-1')
        self.build_babel_egg()
        self.recipe.options['eggs'] = 'Babel'
        self.recipe.install_requirements()  # to get 'ws' attribute
        self.recipe._freeze_egg_versions(conf, 'freeze')
        try:
            version = conf.get('freeze', 'some.distribution')
        except NoOptionError:
            self.fail("Expected version of 'some.distribution' not kept !")
        self.assertEquals(version, '1.0alpha')

    def test_freeze_egg_versions_develop(self):
        """Test that a developped requirement is not dumped in [versions].
        """
        conf = ConfigParser()
        conf.add_section('freeze')
        self.make_recipe(version='6.1-1')
        self.recipe.develop(os.path.join(TEST_DIR, 'fake_babel'))
        self.recipe.options['eggs'] = 'Babel'
        self.recipe.install_requirements()  # to get 'ws' attribute
        self.recipe._freeze_egg_versions(conf, 'freeze')
        self.assertRaises(NoOptionError, conf.get, 'freeze', 'Babel')

    def test_freeze_vcs_source(self):
        self.make_recipe(version='6.1-1')
        b_dir = self.recipe.buildout_dir
        repo_path = os.path.join(b_dir, 'custom')
        subprocess.check_call(['hg', 'init', repo_path])
        with open(os.path.join(repo_path, 'somefile'), 'w') as f:
            f.write('content')
        subprocess.check_call(['hg', '--cwd', repo_path,
                               'commit', '-A', '-m', 'somerev',
                               '-u', COMMIT_USER_FULL,
                               ])

        rev = self.recipe._freeze_vcs_source('hg', repo_path)
        hg = subprocess.Popen(['hg', '--cwd', repo_path, 'diff', '-r', rev],
                              stdout=subprocess.PIPE,
                              stderr=subprocess.PIPE)
        out, err = hg.communicate()
        if hg.returncode or err:
            self.fail("Invalid extracted revision: %r" % rev)
        self.assertEquals(out, '', 'Extracted revision shows some diff')

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

    def test_freeze_vcs_source_dirty(self):
        self.make_recipe(version='6.1-1')
        b_dir = self.recipe.buildout_dir
        repo_path = os.path.join(b_dir, 'custom')
        subprocess.check_call(['hg', 'init', repo_path])
        with open(os.path.join(repo_path, 'somefile'), 'w') as f:
            f.write('content')
        subprocess.check_call(['hg', '--cwd', repo_path,
                               'commit', '-A', '-m', 'somerev',
                               '-u', COMMIT_USER_FULL,
                               ])

        self.recipe.local_modifications = []
        # modification on tracked file
        with open(os.path.join(repo_path, 'somefile'), 'w') as f:
            f.write('changed content')
        self.recipe._freeze_vcs_source('hg', repo_path)
        self.assertTrue(bool(self.recipe.local_modifications))

        subprocess.check_call(['hg', '--cwd', repo_path, 'revert', '--all'])

        # untracked file
        self.recipe.local_modifications = []
        with open(os.path.join(repo_path, 'untracked'), 'w') as f:
            f.write('something else')
        self.recipe._freeze_vcs_source('hg', repo_path)
        self.assertTrue(bool(self.recipe.local_modifications))

    def test_prepare_frozen_buildout(self):
        self.make_recipe(version='6.1-1')
        conf = ConfigParser()
        self.recipe._prepare_frozen_buildout(conf)
        self.assertTrue('buildout' in conf.sections())

    def test_prepare_frozen_buildout_gp_vcsdevelop(self):
        self.make_recipe(version='6.1-1')
        self.recipe.b_options[GP_VCS_EXTEND_DEVELOP] = (
            "fakevcs+http://example.com/aeroolib#egg=aeroolib")

        conf = ConfigParser()
        self.recipe._prepare_frozen_buildout(conf)
        extends_develop = conf.get('buildout', GP_VCS_EXTEND_DEVELOP)
        self.assertEquals(extends_develop.strip(),
                          "fakevcs+http://example.com/aeroolib@fakerev"
                          "#egg=aeroolib")

    def test_prepare_frozen_buildout_gp_vcsdevelop_already_fixed(self):
        """Test that prepare_frozen_buildout understands existing pinning.

        One might say that we souldn't touch an existing revision pinning, but
        a difference can arise from a tag resolution, or simply someone
        manually updating the repo. In all cases, the instrospected revision
        will be used.
        """
        self.make_recipe(version='6.1-1')
        self.recipe.b_options[GP_VCS_EXTEND_DEVELOP] = (
            "fakevcs+http://example.com/aeroolib@somerev#egg=aeroolib")

        conf = ConfigParser()
        self.recipe._prepare_frozen_buildout(conf)
        extends_develop = conf.get('buildout', GP_VCS_EXTEND_DEVELOP)
        self.assertEquals(extends_develop.strip(),
                          "fakevcs+http://example.com/aeroolib@fakerev"
                          "#egg=aeroolib")


class TestExtraction(RecipeTestCase):

    def setUp(self):
        super(TestExtraction, self).setUp()
        self.extract_target_dir = tempfile.mkdtemp('test_recipe_extract')

    def tearDown(self):
        shutil.rmtree(self.extract_target_dir)
        super(TestExtraction, self).tearDown()

    def make_recipe(self, name='openerp', **options):
        self.recipe = TestingRecipe(self.buildout, name, options)

    def test_prepare_extracted_buildout(self):
        self.make_recipe(version='6.1-1')
        conf = ConfigParser()
        self.recipe._prepare_extracted_buildout(conf, self.extract_target_dir)
        self.assertTrue('buildout' in conf.sections())

    def test_extract_addons(self):
        """Test extract_downloads_to about addons ('local' server version).
        """
        target_dir = self.extract_target_dir
        addons = ['local specific',
                  'fakevcs http://some/repo vcs-addons revspec']
        self.make_recipe(version='local mainsoftware',
                         addons=os.linesep.join(addons))

        conf = ConfigParser()
        extracted = set()
        self.recipe._extract_sources(conf, target_dir, extracted)
        addons_opt = set(conf.get('openerp', 'addons').split(os.linesep))
        self.assertEquals(addons_opt,
                          set(('local vcs-addons', 'local specific')))
        self.assertEquals(extracted,
                          set([os.path.join(target_dir, 'vcs-addons')]))

        # no need to override revisions
        self.assertRaises(NoOptionError, conf.get, 'openerp', 'revisions')

        # testing that archival took place for fakevcs, but not for local

        self.failIf(os.path.exists(os.path.join(target_dir, 'specific')),
                    "Local addons dir should not have been extracted")
        # get_update having not been called, it is expected to have the
        # default revision 'fakerev', instead of 'revspec'.
        with open(os.path.join(target_dir, 'vcs-addons',
                               '.fake_archival.txt')) as f:
            self.assertEquals(f.read(), 'fakerev')

    def test_extract_addons_revisions(self):
        """Test extract_downloads_to about revisions overriding.

        In case the source buildout uses the revisions option, it must be
        overridden in the extracted one because it does not make sense with
        the 'local' scheme.
        """
        target_dir = self.extract_target_dir
        addons = ['local specific',
                  'fakevcs http://some/repo vcs-addons revspec']
        self.make_recipe(version='local mainsoftware',
                         addons=os.linesep.join(addons),
                         revisions='vcs-addons 213')

        conf = ConfigParser()
        extracted = set()
        self.recipe._extract_sources(conf, target_dir, extracted)
        self.assertEquals(conf.get('openerp', 'revisions').strip(), '')

    def test_prepare_extracted_buildout_gp_vcsdevelop(self):
        self.make_recipe(version='6.1-1')
        self.recipe.b_options[GP_VCS_EXTEND_DEVELOP] = (
            "fakevcs+http://example.com/aeroolib#egg=aeroolib")
        self.recipe.b_options['develop'] = os.path.join(
            self.recipe.buildout_dir, 'simple_develop')

        conf = ConfigParser()
        self.recipe._prepare_extracted_buildout(conf, self.extract_target_dir)
        extends_develop = conf.get('buildout', GP_VCS_EXTEND_DEVELOP)
        self.assertEquals(extends_develop.strip(), '')
        develop = conf.get('buildout', 'develop').split(os.linesep)
        self.assertEquals(set(d for d in develop if d),
                          set(['aeroolib', 'simple_develop']))

        # extraction has been done
        target = os.path.join(self.extract_target_dir, 'aeroolib')
        self.assertTrue(os.path.exists(target))
        with open(os.path.join(target, '.fake_archival.txt')) as f:
            self.assertEquals(f.read(), 'fakerev')
