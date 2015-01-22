# -*- coding: utf-8 -*-
#
#
#    Authors: Laurent Mignon
#    Copyright (c) 2014 Acsone SA/NV (http://www.acsone.eu)
#
#    This program is free software: you can redistribute it and/or modify
#    it under the terms of the GNU Affero General Public License as
#    published by the Free Software Foundation, either version 3 of the
#    License, or (at your option) any later version.
#
#    This program is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#    GNU Affero General Public License for more details.
#
#    You should have received a copy of the GNU Affero General Public License
#    along with this program.  If not, see <http://www.gnu.org/licenses/>.
#
#
import os
import shutil
import logging
from anybox.recipe.odoo.server import ServerRecipe
from zc.buildout import UserError
from anybox.recipe.odoo.utils import working_directory_keeper
import subprocess

logger = logging.getLogger(__name__)

TXT_EXTENSIONS = ['rst', 'txt', 'markdown', 'md']


class ReleaseRecipe(ServerRecipe):
    """Recipe to build a self-contained and offline playable archive
    """

    def __init__(self, *a, **kw):
        super(ReleaseRecipe, self).__init__(*a, **kw)
        self.offline = True
        opt = self.options
        opt.pop('freeze-to', None)
        opt.pop('extract-downloads-to', None)
        no_extends = self.options.setdefault(
            'no-extends', 'false')
        self.no_extends = no_extends.lower() == 'true'
        # keep a copy of the original eggs list since this one is modified
        # by the recipe
        self.original_eggs = self.options.get('eggs')
        self.__version_file = None

    def install(self):
        self.version = self.get_version_txt()
        if not self.version:
            logger.warning('No version file found (ex: VERSION.txt)')
        else:
            logger.info('Start releasing version %s', self.version)
        self.merge_requirements()
        self.install_requirements()
        release_dir = self._prepare_release_dir()
        self.extract_downloads_to(release_dir)
        self._init_tracking_changes(release_dir)
        self._pack_release(release_dir)
        return self.openerp_installed

    update = install

    def _prepare_release_dir(self):
        opt = self.options
        release_dir = opt.setdefault('release-dir', 'release')
        clean_dir = opt.setdefault('clean-dir', 'false').lower()
        clean_release_dir = clean_dir == 'true'
        if os.path.exists(release_dir):
            if clean_release_dir:
                logger.info("Clean release directory %s", release_dir)
                shutil.rmtree(release_dir)
            else:
                raise UserError('Target dir \'%s\' already exists. '
                                'Delete-it before running or set '
                                '\'clean-dir\' option to true in your config.'
                                '' % release_dir)
        return release_dir

    def _extract_sources(self, out_conf, target_dir, extracted):
        # since our recipe is an extension used to build the release package
        # we need to put the right recipe to use to install the server from
        # the generated configuration
        recipe = self.options.get('recipe', 'anybox.recipe.odoo:release')
        recipe = recipe.replace(':release', ':server')
        self.options['recipe'] = recipe
        vals = super(ReleaseRecipe, self)._extract_sources(
            out_conf, target_dir, extracted)

        # not really the best place to add something to the out_conf in the
        #  new section but the new section in the generated config is created
        # in the base  _extract_soruces and we don't have an other place
        # where it's possible to add options to the new section
        if self.no_extends:
            # if our buildout is standalone, we also need to copy the eggs
            # params
            out_conf.set(self.name, 'eggs', self.original_eggs)
        return vals

    def _prepare_extracted_buildout(self, conf, target_dir):
        super(ReleaseRecipe, self)._prepare_extracted_buildout(
            conf, target_dir)
        # remove the extends directive from buildout section if specified
        # In some case it's usefull to generated a configuration file without
        # dependencies on other other files
        if self.no_extends:
            conf.set('buildout', 'extends', '')

    def extract_downloads_to(self, target_dir, outconf_name='release.cfg'):
        ret = super(ReleaseRecipe, self).extract_downloads_to(
            target_dir, outconf_name)
        if self.version_file:
            shutil.copy(self.version_file, target_dir)
        return ret

    def _init_tracking_changes(self, release_dir):
        opt = self.options
        track_changes = opt.setdefault('track-changes', 'false').lower()
        track_changes = track_changes == 'true'
        if not track_changes:
            return
        logger.info("Init a GIT repository to track changes in %s",
                    release_dir)
        recipe = self.options.get('recipe')
        with working_directory_keeper:
            os.chdir(release_dir)
            subprocess.call(['git', 'init', '.'])
            subprocess.call(
                ['git', 'config', 'user.email', 'release@release.com'])
            subprocess.call(['git', 'config', 'user.name', recipe])
            subprocess.call(['git', 'add', '.'])
            subprocess.call(['git', 'commit', '-m', 'initial'])

    def _pack_release(self, release_dir):
        pack = self.options.setdefault('pack-release', 'false').lower()
        pack = pack == 'true'
        if not pack:
            return
        if self.version:
            arch_file_name = '-'.join([release_dir, self.version])
        else:
            arch_file_name = release_dir
        ret = shutil.make_archive(
            os.path.join(self.buildout_dir, arch_file_name),
            format='gztar', root_dir=self.buildout_dir, base_dir=release_dir,
            logger=logger)
        logger.info('Release packed in %s', ret)
        return ret

    @property
    def version_file(self):
        if self.__version_file:
            return self.__version_file
        for extension in TXT_EXTENSIONS:
            v_file = os.path.join(self.buildout_dir,
                                  '.'.join(['VERSION', extension]))
            if os.path.exists(v_file):
                logger.info('Found version file %s', v_file)
                self.__version_file = v_file
                break
        return self.__version_file

    def get_version_txt(self):
        if self.version_file:
            f = open(self.version_file, 'r')
            version = f.read()
            return self.strip_version(version)
        return None

    def strip_version(self, version):
        """Strip the version of all whitespace."""
        return version.strip().replace(' ', '')
