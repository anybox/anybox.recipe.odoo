from setuptools import setup, find_packages

version = 0.8

setup(
    name = "anybox.recipe.openerp",
    version = version,
    author="Christophe Combelles",
    author_email="ccomb@anybox.fr",
    description="A buildout recipe to install and configure OpenERP",
    license="ZPL",
    long_description=open('README.txt').read() + open('CHANGES.txt').read(),
    url="https://code.launchpad.net/~anybox/+junk/anybox.recipe.openerp",
    packages=find_packages(),
    zip_safe=False,
    include_package_data=True,
    namespace_packages=['anybox', 'anybox.recipe'],
    install_requires=['setuptools',
                      'zc.recipe.egg',
                      'zc.buildout'],
    classifiers=[
      'Framework :: Buildout',
      'Intended Audience :: Developers',
      'Topic :: Software Development :: Build Tools',
      'Topic :: Software Development :: Libraries :: Python Modules',
      ],
    entry_points = {'zc.buildout': [
        'server = anybox.recipe.openerp:Server',
        'webclient = anybox.recipe.openerp:WebClient',
        'gtkclient = anybox.recipe.openerp:GtkClient',
        ]},
    )


