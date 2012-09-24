import os
import sys
from setuptools import setup, find_packages

version = '1.1.1'

if sys.version_info < (2, 6):
    sys.stderr.write("This package requires Python 2.6 or newer. "
                     "Yours is " + sys.version + os.linesep)
    sys.exit(1)

requires = ['setuptools', 'zc.recipe.egg', 'zc.buildout']

setup(
    name = "anybox.recipe.openerp",
    version = version,
    author="Anybox",
    author_email="contact@anybox.fr",
    description="A buildout recipe to install and configure OpenERP",
    license="ZPL",
    long_description=open('README.rst').read() + open('CHANGES.rst').read(),
    url="https://launchpad.net/anybox.recipe.openerp",
    packages=find_packages(),
    zip_safe=False,
    include_package_data=True,
    namespace_packages=['anybox', 'anybox.recipe'],
    install_requires=requires,
    tests_require=requires + ['nose', 'bzr'],
    classifiers=[
      'Development Status :: 4 - Beta',
      'Framework :: Buildout :: Recipe',
      'Intended Audience :: Developers',
      'Topic :: Software Development :: Build Tools',
      'Topic :: Software Development :: Libraries :: Python Modules',
      ],
    entry_points = {'zc.buildout': [
        'server = anybox.recipe.openerp.server:ServerRecipe',
        'webclient = anybox.recipe.openerp.webclient:WebClientRecipe',
        'gtkclient = anybox.recipe.openerp.gtkclient:GtkClientRecipe',
        ]},
    )


