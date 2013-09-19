"""This module bridges the classical ``openerp-server`` as a console script.

The :func:`main` function gets registered on the fly by the server recipe as
a console script entry point and used in particular for ``start_openerp`` and
``test_openerp``.

Some version independence logic for the startup process also get bootstrapped
from here.
"""

import sys
import os
from . import patch_openerp_v5


def insert_args(arguments):
    """Insert ``arguments`` in ``sys.argv`` (direct impact on child script).
    """
    for i, a in enumerate(arguments):
        sys.argv.insert(i+1, a)


def main(starter, conf, version=None, just_test=False):
    """Call the ``starter`` script, dispatching configuration.

    All arguments are set in the standalone script produced by buildout through
    entry point options.

    * ``starter``: path to the main script source file (currently
      ``openerp-server``)
    * ``conf``: path to the OpenERP configuration file (managed by the recipe)
    * ``version``: OpenERP major version
    * ``just_test``: only run unit tests
    """
    arguments = ['-c', conf]

    if just_test:
        arguments.extend(('--log-level',
                          'test' if version >= (6, 0) else 'info',
                          '--stop-after-init'))

        if version >= (7, 0):
            arguments.append('--test-enable')

    insert_args(arguments)

    if version == (5, 0):
        patch_openerp_v5.do_patch()

    os.chdir(os.path.split(starter)[0])
    glob = globals()
    glob['__name__'] = '__main__'
    glob['__file__'] = starter
    execfile(starter, globals())
