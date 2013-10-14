"""Uniform encapsulation of buildout-local upgrade script.

The idea is to provide a common set of options, so that upgrade scripts all
have the same interface, and project maintainers can focus on the decision
taking logic.
"""
import os
import sys
import imp
import logging
from argparse import ArgumentParser
from argparse import ArgumentDefaultsHelpFormatter
from argparse import SUPPRESS
from datetime import datetime
from math import ceil

from .session import Session

DEFAULT_LOG_FILE = 'upgrade.log'


def upgrade(upgrade_script, upgrade_callable, conf, buildout_dir):
    """Run the upgrade from a source file.

    All arguments are set in the standalone script produced by buildout through
    entry point options.

    * ``upgrade_script``: absolute path to the upgrade script python source.
    * ``upgrade_callable``: name of the callable in source file actually
      running the script.

      It must accept the two following positional arguments, in that order:

        - a :class:`.Session` instance (as in standard "OpenERP scripts")
        - a logger (standard object from the :mod:`logging` module)

      and may return a non zero status code to indicate an error.
      Both ``None`` and 0 are interpreted as success.

    * ``conf``: path to the OpenERP configuration file (managed by the recipe)
    * ``buildout_dir``: directory of the buildout
    """

    parser = ArgumentParser(formatter_class=ArgumentDefaultsHelpFormatter,
                            epilog="")
    parser.add_argument('--log-file', default=DEFAULT_LOG_FILE,
                        help="File to log sub-operations to, relative to the "
                        "current working directory, supports homedir "
                        "expansion ('~' on POSIX systems).")
    parser.add_argument('--log-level', default='info',
                        help="Main OpenERP logging level. Does not affect the "
                        "logging from the main upgrade script itself.")
    parser.add_argument('--console-log-level', default='info',
                        help="Level for the upgrade process console "
                        "logging. This is for the main upgrade script itself "
                        "meaning that usually only major steps should be "
                        "logged ")
    parser.add_argument('-q', '--quiet', action='store_true',
                        help="Suppress console output from the main upgrade "
                             "script (lower level stages can still write)")
    parser.add_argument('-d', '--db-name', default=SUPPRESS,
                        help="Database name. If ommitted, the general default "
                        "values from OpenERP config file or libpq will apply.")
    parser.add_argument('--init-load-demo-data', action='store_true',
                        help="Demo data will be loaded with module "
                        "installations if and only if "
                        "this modifier is specified")

    arguments = parser.parse_args()  # 'args' would shadow the one of pdb
    log_path = os.path.abspath(os.path.expanduser(arguments.log_file))
    log_level = arguments.log_level
    console_level = arguments.console_log_level.upper()
    quiet = arguments.quiet

    try:
        log_file = open(log_path, 'a')
    except IOError:
        sys.stderr.write("Cannot open %r for write" % log_path + os.linesep)
        sys.exit(-1)

    session = Session(conf, buildout_dir)

    from openerp.tools import config
    config['logfile'] = log_path
    config['log-level'] = log_level

    start_time = datetime.utcnow()
    if not quiet:
        print("Starting upgrade, logging details to %s at level %s, "
              "and major steps to console at level %s" % (
                  log_path, log_level.upper(), console_level.upper()))
        print('')

    logger = logging.getLogger('openerp.upgrade')
    console_handler = logging.StreamHandler()
    console_handler.setLevel(getattr(logging, console_level))
    console_handler.setFormatter(logging.Formatter(
        "%(asctime)s %(levelname)s  %(message)s"))

    if not arguments.quiet:
        logger.addHandler(console_handler)

    db_name = getattr(arguments, 'db_name', None)
    logger.info("Opening database %r", db_name)
    session.open(db=db_name, with_demo=bool(arguments.init_load_demo_data))
    # actual value after all defaultings have been done
    db_name = session.cr.dbname

    if session.is_initialization:
        logger.info("Database %r base initialization done. Proceeding further",
                    db_name)
    else:
        logger.info("Database %r loaded. Actual upgrade begins.", db_name)

    pkg_version = session.package_version
    if pkg_version is None:
        logger.warn("Expected package version file %r does not exist. "
                    "version won't be set in database at the end of upgrade. "
                    "Consider including such a version file in your project "
                    "*before* version dependent logic is actually needed.",
                    session.version_file_path)
    else:
        logger.info("Read package version: %s from %s", pkg_version,
                    session.version_file_path)

    db_version = session.db_version
    if db_version is None:
        if not session.is_initialization:
            logger.warn("No version currently set in database (the present "
                        "upgrade script has never been run). Consider setting "
                        "database version even for fresh instances, to "
                        "eliminate any guesswork in the upgrade scripts.")
    else:
        logger.info("Database latest upgrade version : %s", db_version)

    upgrade_module = imp.load_source('anybox.recipe.openerp.upgrade_openerp',
                                     upgrade_script)
    statuscode = getattr(upgrade_module, upgrade_callable)(session, logger)
    if statuscode is None or statuscode == 0:
        if pkg_version is not None:
            logger.info("setting version %s in database" % pkg_version)
            session.db_version = pkg_version
        session.cr.commit()

        logger.info("%s successful. Total time: %d seconds." % (
            "Initialization" if session.is_initialization else "Upgrade",
            ceil((datetime.utcnow() - start_time).total_seconds())
        ))
    else:
        logger.error("Please check logs at %s" % log_path)

    log_file.close()
    sys.exit(statuscode)
