"""This module bridges the classical ``openerp-server`` as a console script.

The :func:`main` function gets registered on the fly by the server recipe as
a console script entry point and used in particular for ``start_odoo`` and
``test_odoo``.

Some version independence logic for the startup process also get bootstrapped
from here.
"""

import sys
import os
from . import patch_odoo


def insert_args(arguments):
    """Insert `arguments` in ``sys.argv`` (direct impact on child script).
    """
    for i, a in enumerate(arguments):
        sys.argv.insert(i+1, a)


def main(starter, conf, version=None, just_test=False,
         server_wide_modules=None,
         gevent_script_path=None):
    """Call the `starter` script, dispatching configuration.

    All arguments are set in the standalone script produced by buildout through
    entry point options.

    :param starter: path to the main script source file (currently
      ``openerp-server``)
    :param conf: path to the Odoo configuration file (managed by the recipe)
    :param version: Odoo major version
    :param server_wide_modules: additional server wide modules, to pass with
       the ``--load`` command-line option (ignored if the option is actually
       there on the command line)
    :type version: tuple of integers
    :param just_test: if True, only run unit tests
    """
    arguments = ['-c', conf]

    if just_test:
        arguments.extend(('--log-level',
                          'test' if version >= (6, 0) else 'info',
                          '--stop-after-init'))

        if version >= (7, 0):
            arguments.append('--test-enable')

    if server_wide_modules:
        for opt in sys.argv[1:]:
            if opt.startswith('--load'):
                break
        else:
            arguments.append('--load=' + ','.join(server_wide_modules))

    if '--install-all' in sys.argv:
        sys.argv.remove('--install-all')
        try:
            from openerp.tools import config
            from openerp.modules import get_modules
        except ImportError:
            from odoo.tools import config
            from odoo.modules import get_modules
        # Maybe we should preparse config in all cases and therefore avoid
        # adding the '-c' on the fly ?
        # Still, cautious about pre-6.1 versions
        config.parse_config(['-c', conf])
        arguments.extend(('-i', ','.join(get_modules())))

    insert_args(arguments)

    if version >= (8, 0):  # always true in a.r.odoo, but keeping for now
        assert gevent_script_path is not None
        patch_odoo.do_patch(gevent_script_path)

    os.chdir(os.path.split(starter)[0])
    glob = globals()
    glob['__name__'] = '__main__'
    glob['__file__'] = starter
    sys.argv[0] = starter
    try:
        if sys.version_info < (3, 0):
            execfile(starter, globals())
        else:
            exec(open(starter).read(), globals())
    except SystemExit as exc:
        return exc.code
