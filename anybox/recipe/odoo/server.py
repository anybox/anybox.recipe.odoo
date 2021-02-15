# coding: utf-8
import os
from os.path import join
import sys
import shutil
import logging
import zc.buildout
from zc.buildout import UserError
from .base import BaseRecipe
from . import devtools
from .utils import option_splitlines, option_strip, major_version

logger = logging.getLogger(__name__)

SERVER_COMMA_LIST_OPTIONS = ('log_handler', )


class ServerRecipe(BaseRecipe):
    """Recipe for server install and config
    """
    release_filenames = {
        # no release since OpenERP 6.1, only nightlies
    }

    nightly_filenames = {
        '10.0': 'odoo_10.0.%s.tar.gz',
        'trunk': 'odoo_10.0alpha1.%s.tar.gz'
    }
    """Name of expected nightly tarballs in base URL, by major version.
    """

    recipe_requirements = ('babel',)
    requirements = ('anybox.recipe.odoo',)
    soft_requirements = ('odoo-command',)
    with_gunicorn = False
    with_upgrade = True
    ws = None
    template_upgrade_script = os.path.join(os.path.dirname(__file__),
                                           'upgrade.py.tmpl')
    server_wide_modules = ()

    def __init__(self, *a, **kw):
        super(ServerRecipe, self).__init__(*a, **kw)
        opt = self.options
        self.with_devtools = (
            opt.get('with_devtools', 'false').lower() == 'true')
        self.with_upgrade = self.options.get('upgrade_script') != ''
        # discarding, because we have a special behaviour with custom
        # interpreters
        opt.pop('interpreter', None)
        self.odoo_scripts = {}
        sw_modules = option_splitlines(opt.get('server_wide_modules'))
        if sw_modules and 'web' not in sw_modules:
            sw_modules = ('web', ) + sw_modules
        self.server_wide_modules = sw_modules

        if self.python_scripts_executable:
            # Monkeypatch the script headers to replace the python
            # executable by the one configured by the user
            new_header = '#!%s' % self.python_scripts_executable
            zc.buildout.easy_install.script_template = (
                zc.buildout.easy_install.script_template.replace(
                    zc.buildout.easy_install.script_header, new_header))
            zc.buildout.easy_install.py_script_template = (
                zc.buildout.easy_install.py_script_template.replace(
                    zc.buildout.easy_install.script_header, new_header))

    def apply_version_dependent_decisions(self):
        """Store some booleans depending on detected version.

        Also does some options normalization accordingly.
        Currently, there is only one Odoo version, this method
        will be really useful again in a while.
        """
        gunicorn = self.options.get('gunicorn', '').strip().lower()
        self.with_gunicorn = bool(gunicorn)

        if gunicorn == 'proxied':
            self.options['options.proxy_mode'] = 'True'
            logger.warn("'gunicorn = proxied' now superseded since "
                        "OpenERP 7 by the 'proxy_mode' Odoo server option ")

    def merge_requirements(self, reqs=None):
        """Prepare for installation by zc.recipe.egg

         - develop the odoo distribution and require it
         - gunicorn's related dependencies if needed

        Once 'odoo' is required, zc.recipe.egg will take it into account
        and put it in needed scripts, interpreters etc.

        Historically, in ``anybox.recipe.openerp`` this used to take care
        of adding Pillow, which is now in Odoo's ``setup.py``.
        """
        odoo_dir = getattr(self, 'odoo_dir', None)
        odoo_project_name = 'odoo'
        if odoo_dir is not None:  # happens in unit tests
            odoo_project_name = self.develop(odoo_dir)
        self.requirements.append(odoo_project_name)

        if self.with_gunicorn:
            self.requirements.extend(('psutil', 'gunicorn'))

        if self.with_devtools:
            self.requirements.extend(devtools.requirements)

        BaseRecipe.merge_requirements(self, reqs=reqs)
        return odoo_project_name

    def _create_default_config(self):
        """Have Odoo generate its default config file.
        """
        self.options.setdefault('options.admin_passwd', '')
        sys.path.append(self.odoo_dir)
        sys.path.extend([egg.location for egg in self.ws])

        try:
            from odoo.tools.config import configmanager
        except ImportError:
            from openerp.tools.config import configmanager

        configmanager(self.config_path).save()

    def _create_gunicorn_conf(self, qualified_name):
        """Put a gunicorn_PART.conf.py script in /etc.

        Derived from the standard gunicorn.conf.py shipping with Odoo.
        """
        gunicorn_options = dict(
            workers='4',
            timeout='240',
            max_requests='2000',
            qualified_name=qualified_name,
            bind='%s:%s' % (
                self.options.get('options.xmlrpc_interface', '0.0.0.0'),
                self.options.get('options.xmlrpc_port', '8069')
            ))

        gunicorn_prefix = 'gunicorn.'
        gunicorn_options.update((k[len(gunicorn_prefix):], v)
                                for k, v in self.options.items()
                                if k.startswith(gunicorn_prefix))

        gunicorn_options['server_wide_modules'] = list(
            self.server_wide_modules) if self.server_wide_modules else ['web']

        f = open(join(self.etc, qualified_name + '.conf.py'), 'w')
        conf = """'''Gunicorn configuration script.
Generated by buildout. Do NOT edit.'''
try:
  import openerp as odoo
except ImportError:
  import odoo
bind = %(bind)r
pidfile = %(qualified_name)r + '.pid'
workers = %(workers)s

timeout = %(timeout)s
max_requests = %(max_requests)s

odoo.multi_process = True  # needed even with only one worker
odoo.conf.server_wide_modules = %(server_wide_modules)r
conf = odoo.tools.config
""" % gunicorn_options

        # forwarding specified options
        prefix = 'options.'
        for opt, val in self.options.items():
            if not opt.startswith(prefix):
                continue
            opt = opt[len(prefix):]
            if opt == 'log_level':
                # blindly following the sample script
                val = dict(DEBUG=10, DEBUG_RPC=8, DEBUG_RPC_ANSWER=6,
                           DEBUG_SQL=5, INFO=20, WARNING=30, ERROR=40,
                           CRITICAL=50).get(val.strip().upper(), 30)
            if opt in SERVER_COMMA_LIST_OPTIONS:
                val = [i.strip() for i in val.split(',')]

            conf += 'conf[%r] = %r' % (opt, val) + os.linesep

        preload_dbs = option_splitlines(self.options.get(
            'gunicorn.preload_databases'))
        if preload_dbs:
            conf += os.linesep.join((
                "",
                "def post_fork(server, worker):",
                "    '''Preload databases specified in buildout conf.'''",
                "    from odoo.modules.registry import RegistryManager",
                "    preload_dbs = %r" % (preload_dbs,),
                "    for db_name in preload_dbs:",
                "        server.log.info('Worker loading database %r',",
                "                        db_name)",
                "        RegistryManager.get(db_name)",
                "    server.log.info('Odoo databases %r loaded, '",
                "                    'worker ready '",
                "                    'to serve requests', preload_dbs)",
            ))

        f.write(conf)
        f.close()

    def _get_server_command(self):
        """Return a full path to the main Odoo server command."""
        if major_version(self.version_detected)[0] >= 10:
            base_name = 'odoo-bin'
        else:
            base_name = 'openerp-server'
        return join(self.odoo_dir, base_name)

    def _parse_odoo_scripts(self):
        """Parse required scripts from conf."""

        scripts = self.odoo_scripts
        if 'odoo_scripts' not in self.options:
            return
        for line in option_splitlines(self.options.get('odoo_scripts')):
            line = line.split()

            naming = line[0].split('=')
            if not naming or len(naming) > 2:
                raise UserError("Invalid script specification %r" % line[0])
            elif len(naming) == 1:
                name = '_'.join((naming[0], self.name))
            else:
                name = naming[1]
            cl_options = []
            desc = scripts[name] = dict(entry=naming[0],
                                        command_line_options=cl_options)

            opt_prefix = 'command-line-options='
            arg_prefix = 'arguments='
            log_prefix = 'odoo-log-level='
            for token in line[1:]:
                if token.startswith(opt_prefix):
                    cl_options.extend(token[len(opt_prefix):].split(','))
                elif token.startswith(arg_prefix):
                    desc['arguments'] = token[len(arg_prefix):]
                elif token.startswith(log_prefix):
                    level = token[len(log_prefix):].upper()
                    if level not in dir(logging):
                        raise UserError("In script %r, improper logging "
                                        "level %r" % (name, level))
                    desc['odoo_log_level'] = level
                else:
                    raise UserError(
                        "Invalid token for script %r: %r" % (name, token))

    def _get_or_create_script(self, entry, name=None):
        """Retrieve or create a registered script by its entry point.

        If create_name is not given, no creation will occur, will return
        None if not found.
        In all other cases, return return (script_name, desc).
        """
        for script_name, desc in self.odoo_scripts.items():
            if desc['entry'] == entry:
                return script_name, desc

        if name is not None:
            desc = self.odoo_scripts[name] = dict(entry=entry)
            return name, desc

    def _relativitize(self, path):
        if self._relative_paths:
            return "join(base, %r)" % os.path.relpath(
                path, self._relative_paths)
        return "%r" % path

    def _register_main_startup_script(self, qualified_name):
        """Register main startup script, usually ``start_odoo`` for install.
        """
        desc = self._get_or_create_script('odoo_starter',
                                          name=qualified_name)[1]

        arguments = '%s, %s, version=%r, gevent_script_path=%s' % (
            self._relativitize(self._get_server_command()),
            self._relativitize(self.config_path),
            self.major_version,
            self._relativitize(self.gevent_script_path))

        if self.server_wide_modules:
            arguments += ', server_wide_modules=%r' % (
                self.server_wide_modules,)

        desc.update(arguments=arguments)

        startup_delay = float(self.options.get('startup_delay', 0))

        initialization = ['']
        if self.with_devtools:
            initialization.extend((
                'from anybox.recipe.odoo import devtools',
                'devtools.load(for_tests=False)',
                ''))

        if startup_delay:
            initialization.extend(
                ('print("sleeping %s seconds...")' % startup_delay,
                 'import time',
                 'time.sleep(%f)' % startup_delay))

        desc['initialization'] = os.linesep.join((initialization))

    def _register_test_script(self, qualified_name):
        """Register the main test script for installation.
        """
        desc = self._get_or_create_script('odoo_tester',
                                          name=qualified_name)[1]
        arguments = '%s, %s, version=%r, just_test=True' % (
            self._relativitize(self._get_server_command()),
            self._relativitize(self.config_path),
            self.major_version)
        arguments += ', gevent_script_path=%r' % self._relativitize(
            self.gevent_script_path)

        desc.update(
            entry='odoo_starter',
            initialization=os.linesep.join((
                "from anybox.recipe.odoo import devtools",
                "devtools.load(for_tests=True)",
                "")),
            arguments=arguments
        )

    def _register_upgrade_script(self, qualified_name):
        desc = self._get_or_create_script('odoo_upgrader',
                                          name=qualified_name)[1]
        script_opt = option_strip(self.options.get('upgrade_script',
                                                   'upgrade.py run'))
        script = script_opt.split()
        if len(script) != 2:
            # TODO add console script entry point support
            raise zc.buildout.UserError(
                ("upgrade_script option must take the form "
                 "SOURCE_FILE CALLABLE (got '%r')" % script))
        script_source_path = self.make_absolute(script[0])
        desc.update(
            entry='odoo_upgrader',
            arguments='%s, %r, %r, %r' % (
                self._relativitize(script_source_path), script[1],
                self._relativitize(self.config_path),
                self.buildout_dir),
        )

        if not os.path.exists(script_source_path):
            logger.warning("Ugrade script source %s does not exist."
                           "Initializing it for you", script_source_path)
            shutil.copy(self.template_upgrade_script, script_source_path)

    def _register_gunicorn_startup_script(self, qualified_name):
        """Register a gunicorn foreground start script for installation.

        The produced script is suitable for external process management, such
        as provided by supervisor.
        """
        desc = self._get_or_create_script('gunicorn',
                                          name=qualified_name)[1]

        gunicorn_options = {}
        gunicorn_prefix = 'gunicorn.'
        gunicorn_options.update((k[len(gunicorn_prefix):], v)
                                for k, v in self.options.items()
                                if k.startswith(gunicorn_prefix))

        gunicorn_entry_point = gunicorn_options.get('entry_point')
        if gunicorn_entry_point is None:
            gunicorn_entry_point = ('odoo:'
                                    'service.wsgi_server.application')

        # gunicorn's main() does not take arguments, that's why we have
        # to resort on hacking sys.argv
        desc['initialization'] = (
            "from sys import argv; argv[1:] = ['%s', '-c', '%s.conf.py']" % (
                gunicorn_entry_point,
                self._relativitize(join(self.etc, qualified_name))))

    def _register_gevent_script(self, qualified_name):
        """Register the gevent startup script
        """
        desc = self._get_or_create_script('odoo-gevent',
                                          name=qualified_name)[1]

        initialization = [
            "import gevent.monkey",
            "gevent.monkey.patch_all()",
            "import psycogreen.gevent",
            "psycogreen.gevent.patch_psycopg()",
            ""]

        if self.with_devtools:
            initialization.extend([
                'from anybox.recipe.odoo import devtools',
                'devtools.load(for_tests=False)',
                ''])

        desc['initialization'] = os.linesep.join(initialization)

    def _register_cron_worker_startup_script(self, qualified_name):
        """Register the cron worker script for installation.

        This worker script has been introduced in openobject-server, rev 4184
        together with changes in the main code that it requires.
        These changes appeared in nightly build 6.1-20120530-233414.
        The worker script itself does not appear in nightly builds.
        """
        script_src = join(self.odoo_dir, 'odoo-cron-worker')
        if not os.path.isfile(script_src):
            version = self.version_detected
            if self.version_wanted == '6.1-1' or (
                    version.startswith('6.1-2012') and
                    version[4:12] < '20120530'):
                logger.warn(
                    "Can't use odoo-cron-worker with version %s "
                    "You have to run a separate regular Odoo process "
                    "for cron jobs to be launched.", version)
                return

            logger.info("Cron launcher odoo-cron-worker not found in "
                        "odoo source tree (version %s). "
                        "This is expected with some nightly builds. "
                        "Using the launcher script distributed "
                        "with the recipe.", version)
            script_src = join(os.path.split(__file__)[0],
                              'odoo-cron-worker')

        desc = self._get_or_create_script('odoo_cron_worker',
                                          name=qualified_name)[1]
        desc.update(entry='odoo_cron_worker',
                    arguments='%s, %s' % (
                        self._relativitize(script_src),
                        self._relativitize(self.config_path)),
                    initialization='',
                    )

    def _install_interpreter(self):
        """Install a python interpreter with a ready-made session object."""
        int_name = self.options.get('interpreter_name', None)
        if int_name == '':  # conf requires not to build an interpreter
            return
        elif int_name is None:
            int_name = 'python_' + self.name

        initialization = os.linesep.join((
            "",
            "from anybox.recipe.odoo.runtime.session import Session",
            "session = Session(%s, base)" % self._relativitize(
                self.config_path),
            "if len(sys.argv) <= 1:",
            "    print('To start the Odoo working session, just do:')",
            "    print('    session.open(db=DATABASE_NAME)')",
            "    print('or, to use the database from the buildout "
            "part config:')",
            "    print('    session.open()')",
            "    print('All other options from buildout part config "
            "do apply.')",
            ""
            "    print('Then you can issue commands such as:')",
            "    print(\""
            "    session.registry('res.users').browse(session.cr, 1, 1)\")",
            "    try:",
            "        from openerp import release",
            "    except ImportError:",
            "        from odoo import release",
            "    from anybox.recipe.odoo.utils import major_version",
            "    if major_version(release.version)[0] >= 8:",
            "        print('Or using new api:')",
            "        print(\"    session.env['res.users'].browse(1)\")"
            ""))

        reqs, ws = self.eggs_reqs, self.eggs_ws
        return zc.buildout.easy_install.scripts(
            reqs, ws, sys.executable, self.options['bin-directory'],
            scripts={},
            interpreter=int_name,
            initialization=initialization,
            arguments=self.options.get('arguments', ''),
            extra_paths=self.extra_paths,
            relative_paths=self._relative_paths,
        )

    def _install_odoo_scripts(self):
        """Install scripts registered in self.odoo_scripts.

        If initialization string is not passed, one will be cooked for
          - session initialization
          - treatment of Odoo options specific to this script, as required
            in the 'options' key of the scripts descrition (typically to
            add a database opening option to the provided script).
        """
        reqs, ws = self.eggs_reqs, self.eggs_ws

        common_init = os.linesep.join((
            "",
            "from anybox.recipe.odoo.runtime.session import Session",
            "session = Session(%s, base)" % self._relativitize(
                self.config_path)))

        for script_name, desc in self.odoo_scripts.items():
            initialization = desc.get('initialization', common_init)
            log_level = desc.get('odoo_log_level')
            if log_level:
                initialization = os.linesep.join((
                    initialization,
                    "import logging",
                    "logging.getLogger('odoo').setLevel"
                    "(logging.%s)" % log_level))
            options = desc.get('command_line_options')
            if options:
                initialization = os.linesep.join((
                    initialization,
                    "session.handle_command_line_options(%r)" % options))

            zc.buildout.easy_install.scripts(
                reqs, ws, sys.executable, self.bin_dir,
                scripts={desc['entry']: script_name},
                interpreter='',
                initialization=initialization,
                arguments=desc.get('arguments', ''),
                extra_paths=self.extra_paths,
                relative_paths=self._relative_paths,
            )
            self.odoo_installed.append(join(self.bin_dir, script_name))

    def _install_startup_scripts(self):
        """install startup and control scripts.
        """
        self._parse_odoo_scripts()

        # provide additional needed entry points for main start/test scripts
        self.eggs_reqs.extend((
            ('odoo_starter',
             'anybox.recipe.odoo.runtime.start_odoo',
             'main'),
            ('odoo_cron_worker',
             'anybox.recipe.odoo.runtime.start_odooo',
             'main'),
            ('odoo_upgrader',
             'anybox.recipe.odoo.runtime.upgrade',
             'upgrade'),
        ))

        if major_version(self.version_detected)[0] >= 10:
            self.eggs_reqs.append(
                ('odoo-gevent', 'odoo.cli', 'main'),
            )
        else:
            self.eggs_reqs.append(
                ('odoo-gevent', 'openerp.cli', 'main'),
            )
        self._install_interpreter()

        main_script = self.options.get('script_name', 'start_' + self.name)
        gevent_script_name = self.options.get('gevent_script_name',
                                              'gevent_%s' % self.name)
        self._register_gevent_script(gevent_script_name)
        self.gevent_script_path = join(self.bin_dir, gevent_script_name)

        self._register_main_startup_script(main_script)
        self.script_path = join(self.bin_dir, main_script)

        if self.with_devtools:
            self._register_test_script(
                self.options.get('test_script_name', 'test_' + self.name))

        if self.with_gunicorn:
            qualified_name = self.options.get('gunicorn_script_name',
                                              'gunicorn_%s' % self.name)
            self._create_gunicorn_conf(qualified_name)
            self._register_gunicorn_startup_script(qualified_name)

            qualified_name = self.options.get('cron_worker_script_name',
                                              'cron_worker_%s' % self.name)
            self._register_cron_worker_startup_script(qualified_name)

        if self.with_upgrade:
            qualified_name = self.options.get('upgrade_script_name',
                                              'upgrade_%s' % self.name)
            self._register_upgrade_script(qualified_name)

        self._install_odoo_scripts()
