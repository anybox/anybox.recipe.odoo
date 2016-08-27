# flake8: noqa

from setuptools import setup, find_packages

setup(
    name='Babel',
    version='0.123',  # unlikely to exist ever
    description='Fake Babel',
    long_description="Satisfies hardcoded deps to babel, not to be "
                     "used to test versions, freeze etc.",
    author='',
    author_email='',
    zip_safe=False,
    packages=find_packages(),
)
