# -*- coding: utf-8 -

from setuptools import setup, find_packages

setup(
    name = 'openerp-command',
    version = '0.0.0',
    description = 'Fake openerp-command',
    long_description = 'Fake openerp-command',
    author = '',
    author_email = '',
    zip_safe = False,
    packages = find_packages(),
    entry_points="""
    [console_scripts]
	oe=openerpcommand:main
    """,
)
