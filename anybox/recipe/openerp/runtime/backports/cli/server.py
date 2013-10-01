# -*- coding: utf-8 -*-

##############################################################################
#
#    OpenERP, Open Source Management Solution
#    Copyright (C) 2004-2009 Tiny SPRL (<http://tiny.be>).
#
#    This program is free software: you can redistribute it and/or modify
#    it under the terms of the GNU Affero General Public License as
#    published by the Free Software Foundation, either version 3 of the
#    License, or (at your option) any later version.
#
#    This program is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#    GNU Affero General Public License for more details.
#
#    You should have received a copy of the GNU Affero General Public License
#    along with this program.  If not, see <http://www.gnu.org/licenses/>.
#
##############################################################################
#
# anybox.recipe.openerp is also under AGPL v3+
#

"""
Copied from OpenERP 6.1's openerp-server startup script.

This makes utilitary functions available to the session module.
"""

import logging
import os
import sys

try:
    import openerp
except:
    # this file must stay importable by nose tests
    pass
else:
    __author__ = openerp.release.author
    __version__ = openerp.release.version

    if openerp.release.version_info < (6, 1):
        raise RuntimeError("Interpreter and scripts not compatible "
                           "with OpenERP < 6.1")

# Also use the `openerp` logger for the main script.
_logger = logging.getLogger('openerp')


def check_root_user():
    """ Exit if the process's user is 'root' (on POSIX system)."""
    if os.name == 'posix':
        import pwd
        if pwd.getpwuid(os.getuid())[0] == 'root':
            sys.stderr.write("Running as user 'root' is a security risk, "
                             "aborting.\n")
            sys.exit(1)


def check_postgres_user():
    """ Exit if the configured database user is 'postgres'.

    This function assumes the configuration has been initialized.
    """
    config = openerp.tools.config
    if config['db_user'] == 'postgres':
        sys.stderr.write("Using the database user 'postgres' is a "
                         "security risk, aborting.")
        sys.exit(1)


def report_configuration():
    """ Log the server version and some configuration values.

    This function assumes the configuration has been initialized.
    """
    config = openerp.tools.config
    _logger.info("OpenERP version %s", __version__)
    for name, value in [('addons paths', config['addons_path']),
                        ('database hostname',
                         config['db_host'] or 'localhost'),
                        ('database port', config['db_port'] or '5432'),
                        ('database user', config['db_user'])]:
        _logger.info("%s: %s", name, value)
