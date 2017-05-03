"""Necessary monkey patches to make Odoo work in the buildout context.
"""

import subprocess


def do_patch(gevent_script_path):
    """
    Patch odoo prefork so that --workers execute the correct gevent script.

    This monkey patch could be safer, if the script path determination could be
    isolated from the actual process management logic in the original.
    """

    try:
        from odoo.service.server import PreforkServer, stripped_sys_argv
        from odoo.release import version_info
    except ImportError:
        from openerp.service.server import PreforkServer, stripped_sys_argv
        from openerp.release import version_info

    def long_polling_spawn(server):
        nargs = stripped_sys_argv()
        nargs[0] = gevent_script_path
        if version_info[0] >= 10:
            nargs.insert(1, 'gevent')
        popen = subprocess.Popen(nargs)
        server.long_polling_pid = popen.pid

    PreforkServer.long_polling_spawn = long_polling_spawn
