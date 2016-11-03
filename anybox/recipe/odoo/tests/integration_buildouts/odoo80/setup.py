# -*- coding: utf-8 -*-
# flake8: noqa

# setup.py from odoo 8.0 alpha, included as is, except for the dependencies

##############################################################################
#
#    OpenERP, Open Source Management Solution
#    Copyright (C) 2004-2010 Tiny SPRL (<http://tiny.be>).
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
##############################################################################

import glob, os, re, setuptools, sys
from os.path import join

# List all data files
def data():
    return []

def gen_manifest():
    file_list="\n".join(data())
    open('MANIFEST','w').write(file_list)

execfile(join(os.path.dirname(__file__), 'openerp', 'release.py'))

# Notes for OpenERP developer on windows:
#
# To setup a windows developer evironement install python2.7 then pip and use
# "pip install <depencey>" for every dependency listed below.
#
# Dependecies that requires DLLs are not installable with pip install, for
# them we added comments with links where you can find the installers.
#
# OpenERP on windows also require the pywin32, the binary can be found at
# http://pywin32.sf.net
#
# Both python2.7 32bits and 64bits are known to work.

setuptools.setup(
      name             = 'openerp',
      version          = version,
      description      = description,
      long_description = long_desc,
      url              = url,
      author           = author,
      author_email     = author_email,
      classifiers      = filter(None, classifiers.split("\n")),
      license          = license,
      scripts          = ['openerp-server', 'openerp-gevent', 'odoo.py'],
      data_files       = data(),
      packages         = setuptools.find_packages(),
      dependency_links = [],
      #include_package_data = True,
      # GR voided the list, because we're interested in the test in what
      # the recipe will add
      install_requires = [],
      extras_require = {},
      tests_require = [],
)


# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
