"""Full zc.buildout oriented integration tests.

These are "whole loop" tests with respect to zc.buildout, but not at all with
respect to Odoo. For the latter, check the ``tests_with_odoo`` top directory
of this repository.
"""

import os
import sys
import unittest
import shutil
from pkg_resources import working_set, Requirement
from copy import deepcopy
from tempfile import mkdtemp

from zc.buildout import buildout
from zc.buildout.easy_install import Installer, buildout_and_setuptools_path

TEST_DIR = os.path.dirname(__file__)
EGG_SUFFIX = '-py%d.%d.egg' % sys.version_info[:2]


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
            self.provide_dependencies()
        except:
            self.tearDown()
            raise

    def provide_dependencies(self):
        """Add paths for resolution from inner buildout's Environment.

        These paths tend to vary according to the way anybox.recipe.odoo has
        been installed, notably there's a big difference between issueing in a
        virtualenv ``python setup.py develop`` and
        ``python setup.py develop --upgrade```, the latter putting the
        dependencies into separate egg directories below the virtualenv's
        ``site-packages`` while the former installs straight into
        ``site-packages``.

        For now we monkey-patch the path lists that ``zc.buildout`` uses
        to provide setuptools in all cases, based on a list of all needed
        dependencies, meaning that this list will have to be maintained.

        Alternatives to consider :

        * inject the whole current ``sys.path``
        * play with the sub-buildout's ``find-links`` options

        The monkey-patching in itself is tolerable in that the main purpose of
        these integration tests is to report about the impact of internal
        changes to to zc.buildout anyway.
        """

        autopath = buildout_and_setuptools_path
        self.autopath_original = autopath[:]
        forward_projects = ['pip', 'zc.buildout', 'zc.recipe.egg',
                            'anybox.recipe.odoo']
        if sys.version_info < (2, 7):
            forward_projects.extend(('argparse', 'ordereddict'))
        autopath.extend(working_set.find(Requirement.parse(project)).location
                        for project in forward_projects)

    def tearDown(self):
        try:
            shutil.rmtree(self.sandbox_dir)
        except:
            pass

        sys.modules['pip'] = self.pip_original
        Installer._versions = self.versions_original
        buildout_and_setuptools_path[:] = self.autopath_original
        os.chdir(self.cwd_original)

    def test_requirements_file_integration_with_versions(self):
        """Versions have precedence."""
        buildout.main(['bootstrap'])
        buildout.main(['-c', 'buildout_with_versions.cfg', 'install', 'odoo'])

        with open(os.path.join('bin', 'start_odoo')) as f:
            start_odoo = f.read()
        self.assertTrue('foobar-0.0.4' + EGG_SUFFIX in start_odoo)
        self.assertFalse('foobar-0.0.3'in start_odoo)

    def test_requirements_file_integration(self):
        """Requirements.txt is applied."""
        buildout.main(['bootstrap'])
        buildout.main(['-c', 'buildout.cfg', 'install', 'odoo'])

        with open(os.path.join('bin', 'start_odoo')) as f:
            start_odoo = f.read()
        self.assertTrue('foobar-0.0.3' + EGG_SUFFIX in start_odoo)
        self.assertFalse('foobar-0.0.4'in start_odoo)
