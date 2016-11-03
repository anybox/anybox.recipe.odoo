# -*- coding: utf-8 -

from setuptools import setup, find_packages

setup(
    name='gunicorn',
    version='0.0.0',
    description='Fake Gunicorn',
    long_description='Fake Gunicorn',
    author='',
    author_email='',
    zip_safe=False,
    packages=find_packages(),
    entry_points="""
    [console_scripts]
    gunicorn=gunicorn:main
    """,
)
