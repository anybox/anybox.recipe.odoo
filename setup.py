from setuptools import setup, find_packages

version = 0.1

setup(
    name = "anybox.recipe.openerp",
    version = version,
    author="Christophe Combelles",
    author_email="ccomb@free.fr",
    description="A buildout recipe to install OpenERP",
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
    entry_points = {'zc.buildout': ['default = anybox.recipe.openerp:Server']},
    )


