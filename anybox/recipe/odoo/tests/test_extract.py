import os
import shutil
import tempfile
from ConfigParser import ConfigParser, NoOptionError
from ..base import GP_VCS_EXTEND_DEVELOP
from ..base import GP_DEVELOP_DIR
from ..testing import RecipeTestCase


class TestExtraction(RecipeTestCase):

    test_dir = os.path.dirname(__file__)

    def setUp(self):
        super(TestExtraction, self).setUp()
        self.extract_target_dir = tempfile.mkdtemp('test_recipe_extract')

    def tearDown(self):
        shutil.rmtree(self.extract_target_dir)
        super(TestExtraction, self).tearDown()

    def make_recipe(self, **kwargs):
        kwargs.setdefault('recipe', 'anybox.recipe.odoo:testrecipe')
        super(TestExtraction, self).make_recipe(**kwargs)

    def test_prepare_extracted_buildout(self):
        self.make_recipe(version='10.0')
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
        addons_opt = set(conf.get('odoo', 'addons').split(os.linesep))
        self.assertEquals(addons_opt,
                          set(('local vcs-addons', 'local specific')))
        self.assertEquals(extracted,
                          set([os.path.join(target_dir, 'vcs-addons')]))

        # no need to override revisions
        self.assertRaises(NoOptionError, conf.get, 'odoo', 'revisions')

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
        self.assertEquals(conf.get('odoo', 'revisions').strip(), '')

    def test_prepare_extracted_buildout_gp_vcsdevelop(self):
        self.make_recipe(version='10.0')
        self.recipe.b_options[GP_VCS_EXTEND_DEVELOP] = (
            "fakevcs+http://example.com/aeroolib#egg=aeroolib")
        self.recipe.b_options['develop'] = os.path.join(
            self.recipe.buildout_dir, 'simple_develop')
        self.recipe.b_options['extensions'] = 'gp.vcsdevelop\n somotherext'

        conf = ConfigParser()
        self.recipe._prepare_extracted_buildout(conf, self.extract_target_dir)
        self.assertFalse(conf.has_option('buildout', GP_VCS_EXTEND_DEVELOP))
        self.assertEqual(conf.get('buildout', 'extensions'), 'somotherext')

        develop = conf.get('buildout', 'develop').split(os.linesep)
        self.assertEquals(set(d for d in develop if d),
                          set(['aeroolib', 'simple_develop']))

        # extraction has been done
        target = os.path.join(self.extract_target_dir, 'aeroolib')
        self.assertTrue(os.path.exists(target))
        with open(os.path.join(target, '.fake_archival.txt')) as f:
            self.assertEquals(f.read(), 'fakerev')

    def test_prepare_extracted_buildout_gp_vcsdevelop_develop_dir(self):
        self.make_recipe(version='10.0')
        self.recipe.b_options[GP_VCS_EXTEND_DEVELOP] = (
            "fakevcs+http://example.com/aeroolib#egg=aeroolib")
        self.recipe.b_options[GP_DEVELOP_DIR] = 'src'
        self.recipe.b_options['develop'] = os.path.join(
            self.recipe.buildout_dir, 'simple_develop')
        self.recipe.b_options['extensions'] = 'gp.vcsdevelop\n somotherext'

        conf = ConfigParser()
        self.recipe._prepare_extracted_buildout(conf, self.extract_target_dir)
        self.assertFalse(conf.has_option('buildout', GP_VCS_EXTEND_DEVELOP))
        self.assertFalse(conf.has_option('buildout', GP_DEVELOP_DIR))
        self.assertEqual(conf.get('buildout', 'extensions'), 'somotherext')

        develop = conf.get('buildout', 'develop').split(os.linesep)
        self.assertEquals(set(d for d in develop if d),
                          set(['src/aeroolib', 'simple_develop']))

        # extraction has been done
        target = os.path.join(self.extract_target_dir, 'src', 'aeroolib')
        self.assertTrue(os.path.exists(target))
        with open(os.path.join(target, '.fake_archival.txt')) as f:
            self.assertEquals(f.read(), 'fakerev')

    def test_prepare_extracted_buildout_remove_bzr(self):
        self.make_recipe(version='local mainsoftware')
        target_dir = self.extract_target_dir
        self.recipe.options['recipe'] = 'anybox.recipe.odoo[bzr]:server'

        conf = ConfigParser()
        self.recipe._extract_sources(conf, target_dir, set())
        self.assertEqual(conf.get(self.recipe.name, 'recipe'),
                         'anybox.recipe.odoo:server')

    def test_prepare_extracted_buildout_keep_other_extras(self):
        self.make_recipe(version='local mainsoftware')
        target_dir = self.extract_target_dir
        self.recipe.options['recipe'] = 'anybox.recipe.odoo[bzr,other]:server'

        conf = ConfigParser()
        self.recipe._extract_sources(conf, target_dir, set())
        self.assertEqual(conf.get(self.recipe.name, 'recipe'),
                         'anybox.recipe.odoo[other]:server')

    def test_prepare_extracted_buildout_no_extras(self):
        self.make_recipe(version='local mainsoftware')
        target_dir = self.extract_target_dir
        self.recipe.options['recipe'] = 'anybox.recipe.odoo:server'

        conf = ConfigParser()
        self.recipe._extract_sources(conf, target_dir, set())
        self.assertEqual(conf.get(self.recipe.name, 'recipe'),
                         'anybox.recipe.odoo:server')

    def test_extract_downloads_to(self):
        """Test the whole freeze method."""

        self.make_recipe(
            version='pr_fakevcs http://main.soft.example odooo refspec',
            addons="pr_fakevcs http://repo.example target rev1\n"
            "local somwehere\n"
            "pr_fakevcs http://repo2.example stdln rev2 group=stdl\n"
            "pr_fakevcs http://repo2.example stdln2 rev2 group=stdl"
        )
        os.mkdir(self.recipe.parts)
        os.mkdir(os.path.join(self.recipe.odoo_dir))
        self.recipe.retrieve_main_software()
        self.recipe.retrieve_addons()
        self.fill_working_set(fictive=True)

        self.recipe.extract_downloads_to(self.extract_target_dir)
        ext_conf = ConfigParser()
        ext_conf.read(os.path.join(self.extract_target_dir, 'release.cfg'))

        # notice standalone handling :
        self.assertEqual(ext_conf.get('odoo', 'addons').splitlines(),
                         ['local target', 'local somwehere',
                          'local stdl'])

        self.assertEqual(ext_conf.get('odoo', 'version').strip(),
                         'local parts/odooo')
        self.assertEqual(ext_conf.get('versions', self.fictive_name),
                         self.fictive_version)
