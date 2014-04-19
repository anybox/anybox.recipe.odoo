import os
import sys
from setuptools import setup, find_packages

version = '1.8.3'

if sys.version_info < (2, 6):
    sys.stderr.write("This package requires Python 2.6 or newer. "
                     "Yours is " + sys.version + os.linesep)
    sys.exit(1)

requires = ['setuptools', 'zc.recipe.egg', 'zc.buildout']

if sys.version_info < (2, 7):
    requires.append('ordereddict')
    requires.append('argparse')

setup(
    name="anybox.recipe.openerp",
    version=version,
    author="Anybox",
    author_email="contact@anybox.fr",
    description="A buildout recipe to install and configure OpenERP",
    license="AGPLv3+",
    long_description='\n'.join((
        open('README.rst').read(),
        open('CHANGES.rst').read())),
    url="https://launchpad.net/anybox.recipe.openerp",
    packages=find_packages(),
    zip_safe=False,
    include_package_data=True,
    install_requires=requires,
    tests_require=requires + ['nose', 'bzr'],
    classifiers=[
        'Development Status :: 5 - Production/Stable',
        'Framework :: Buildout :: Recipe',
        'Intended Audience :: Developers',
        'Intended Audience :: System Administrators',
        'License :: OSI Approved :: GNU Affero General Public License v3 or '
        'later (AGPLv3+)',
        'Topic :: Software Development :: Build Tools',
        'Topic :: Software Development :: Libraries :: Python Modules',
    ],
    entry_points={'zc.buildout': [
        'server = anybox.recipe.openerp.server:ServerRecipe',
        'webclient = anybox.recipe.openerp.webclient:WebClientRecipe',
        'gtkclient = anybox.recipe.openerp.gtkclient:GtkClientRecipe',
    ]},
    extras_require = {
      'bzr' : ['bzr'] },
)
