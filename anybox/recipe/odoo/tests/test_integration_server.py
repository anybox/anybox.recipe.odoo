"""Full zc.buildout oriented integration tests.

These are "whole loop" tests with respect to zc.buildout, but not at all with
respect to Odoo. For the latter, check the ``tests_with_openerp`` top directory
of this repository.
"""

import os
import sys
import unittest
import shutil
from copy import deepcopy
from tempfile import mkdtemp

from zc.buildout import buildout
from zc.buildout.easy_install import Installer

TEST_DIR = os.path.dirname(__file__)


class IntegrationTestCase(unittest.TestCase):

    def setUp(self):
        import pip as pip_original
        self.versions_original = deepcopy(Installer._versions)
        self.cwd_original = os.getcwd()
        self.pip_original = pip_original

        try:
            sandbox = mkdtemp('test_int_oerp_base_recipe')
            self.buildout_dir = os.path.join(sandbox, 'buildout_dir')
            shutil.copytree(os.path.join(TEST_DIR, 'integration_buildouts'),
                            self.buildout_dir)
            os.chdir(self.buildout_dir)
        except:
            self.tearDown()
            raise

    def tearDown(self):
        try:
            shutil.rmtree(self.sandbox_dir)
        except:
            pass

        sys.modules['pip'] = self.pip_original
        Installer._versions = self.versions_original
        os.chdir(self.cwd_original)

    def test_requirements_file_integration_with_versions(self):
        """Versions have precedence."""
        buildout.main(['bootstrap'])
        buildout.main(['-c', 'buildout_with_versions.cfg', 'install', 'odoo'])

        with open(os.path.join('bin', 'start_odoo')) as f:
            start_odoo = f.read()
        self.assertTrue('foobar-0.0.4-py2.7.egg' in start_odoo)
        self.assertFalse('foobar-0.0.3'in start_odoo)

    def test_requirements_file_integration(self):
        """Requirements.txt is applied."""
        buildout.main(['bootstrap'])
        buildout.main(['-c', 'buildout.cfg', 'install', 'odoo'])

        with open(os.path.join('bin', 'start_odoo')) as f:
            start_odoo = f.read()
        self.assertTrue('foobar-0.0.3-py2.7.egg' in start_odoo)
        self.assertFalse('foobar-0.0.4'in start_odoo)
