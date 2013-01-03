# coding: utf-8
import os
from os.path import join
import sys, logging
import subprocess
import zc.buildout
from anybox.recipe.openerp import devtools
from anybox.recipe.openerp.base import BaseRecipe

logger = logging.getLogger(__name__)

class ServerRecipe(BaseRecipe):
    """Recipe for server install and config
    """
    archive_filenames = { '6.0': 'openerp-server-%s.tar.gz',
                         '6.1': 'openerp-%s.tar.gz'}
    archive_nightly_filenames = {
        '6.1': 'openerp-6.1-%s.tar.gz',
        '7.0': 'openerp-7.0-%s.tar.gz',
        'trunk': 'openerp-6.2dev-%s.tar.gz'
        }
    recipe_requirements = ('babel',)
    requirements = ('pychart', 'anybox.recipe.openerp')
    soft_requirements = ('openerp-command',)
    with_openerp_command = False
    with_gunicorn = False
    ws = None

    def __init__(self, *a, **kw):
        super(ServerRecipe, self).__init__(*a, **kw)
        opt = self.options
        self.with_devtools = (
            opt.get('with_devtools', 'false').lower() == 'true')

        self.missing_deps_instructions.update({
            'openerp-command': ("Please provide it with 'develop' or "
                                "'gp.vcsdevelop'. "
                                "You may download it on "
                                "https://launchpad.net/openerp-command."),
            })

    def apply_version_dependent_decisions(self):
        """Store some booleans depending on detected version.

        Also does some options normalization accordingly.
        """
        gunicorn = self.options.get('gunicorn', '').strip().lower()
        self.with_gunicorn = bool(gunicorn)

        if gunicorn and self.major_version == (6, 1):
            entries = dict(direct='core', proxied='proxied')
            self.gunicorn_entry = entries.get(gunicorn)
            assert self.gunicorn_entry is not None, (
                "In OpenERP 6.1, gunicorn option value must be "
                "one of %r" % entries.keys())
        elif self.major_version >= (6, 2) and gunicorn == 'proxied':
            self.options['options.proxy_mode'] = 'True'
            logger.warn("'gunicorn = proxied' now superseded in this OpenERP "
                        "version by the 'proxy_mode' OpenERP server option ")

        self.with_openerp_command = (self.with_devtools
                                     and self.major_version >= (6, 2))

    def merge_requirements(self):
        """Prepare for installation by zc.recipe.egg

         - add Pillow iff PIL not present in eggs option.
         - (OpenERP >= 6.1) develop the openerp distribution and require it
         - gunicorn's related dependencies if needed

        For PIL, extracted requirements are not taken into account. This way,
        if at some point, 
        OpenERP introduce a hard dependency on PIL, we'll still install Pillow.
        The only case where PIL will have precedence over Pillow will thus be
        the case of a legacy buildout.
        See https://bugs.launchpad.net/anybox.recipe.openerp/+bug/1017252

        Once 'openerp' is required, zc.recipe.egg will take it into account
        and put it in needed scripts, interpreters etc.
        """
        setup_has_pil = False
        if not 'PIL' in self.options.get('eggs', '').split():
            if 'PIL' in self.requirements:
                setup_has_pil = True
                self.requirements.remove('PIL')
            self.requirements.append('Pillow')
        if self.major_version >= (6, 1):
            openerp_dir = getattr(self, 'openerp_dir', None)
            if openerp_dir is not None: # happens in unit tests
                self.develop(openerp_dir, setup_has_pil=setup_has_pil)
            self.requirements.append('openerp')

        if self.with_gunicorn:
            self.requirements.extend(('psutil','gunicorn'))

        if self.with_devtools:
            self.requirements.extend(devtools.requirements)

        if self.with_openerp_command:
            self.requirements.append('openerp-command')

        BaseRecipe.merge_requirements(self)

    def _create_default_config(self):
        """Have OpenERP generate its default config file.
        """
        self.options.setdefault('options.admin_passwd', '')
        if self.major_version == (6, 0):
            # root-path not available as command-line option
            os.chdir(join(self.openerp_dir, 'bin'))
            subprocess.check_call([self.script_path, '--stop-after-init', '-s',
                                   ])
        else:
            sys.path.extend([self.openerp_dir])
            sys.path.extend([egg.location for egg in self.ws])
            from openerp.tools.config import configmanager
            configmanager(self.config_path).save()

    def _create_gunicorn_conf(self, qualified_name):
        """Put a gunicorn_PART.conf.py script in /etc.

        Derived from the standard gunicorn.conf.py shipping with OpenERP.
        """
        gunicorn_options = dict(workers='4',
                                timeout='240',
                                max_requests='2000',
                                qualified_name=qualified_name,
                                bind='%s:%s' % (
                self.options.get('options.xmlrpc_interface', '0.0.0.0'),
                self.options.get('options.xmlrpc_port', '8069')))

        gunicorn_prefix = 'gunicorn.'
        gunicorn_options.update((k[len(gunicorn_prefix):], v)
                                for k, v in self.options.items()
                                if k.startswith(gunicorn_prefix))

        f = open(join(self.etc, qualified_name + '.conf.py'), 'w')
        conf = """'''Gunicorn configuration script.
Generated by buildout. Do NOT edit.'''
import openerp
bind = %(bind)r
pidfile = %(qualified_name)r + '.pid'
workers = %(workers)s

if openerp.release.major_version == '6.1':
    on_starting = openerp.wsgi.core.on_starting
    try:
      when_ready = openerp.wsgi.core.when_ready
    except AttributeError: # not in current head of 6.1
      pass
    pre_request = openerp.wsgi.core.pre_request
    post_request = openerp.wsgi.core.post_request

timeout = %(timeout)s
max_requests = %(max_requests)s

openerp.conf.server_wide_modules = ['web']
conf = openerp.tools.config
""" % gunicorn_options

        # forwarding specified options
        prefix = 'options.'
        for opt, val in self.options.items():
            if not opt.startswith(prefix):
                continue
            if opt == 'options.log_level':
                # blindly following the sample script
                val = dict(DEBUG=10, DEBUG_RPC=8, DEBUG_RPC_ANSWER=6,
                           DEBUG_SQL=5, INFO=20, WARNING=30, ERROR=40,
                           CRITICAL=50).get(val.strip().upper(), 30)

            conf += 'conf[%r] = %r' % (opt[len(prefix):], val) + os.linesep
        f.write(conf)
        f.close()

    def _install_gunicorn_startup_script(self, qualified_name):
        """Install a gunicorn foreground start script.

        The produced script is suitable for external process management, such
        as provided by supervisor.
        The script installation works by a tweaked call to a dedicated
        instance of zc.recipe.eggs:scripts.
        """
        options = self.options.copy()
        options['scripts'] = 'gunicorn=' + qualified_name
        options['dependent-scripts'] = 'false'

        gunicorn_options = {}
        gunicorn_prefix = 'gunicorn.'
        gunicorn_options.update((k[len(gunicorn_prefix):], v)
                                for k, v in self.options.items()
                                if k.startswith(gunicorn_prefix))

        gunicorn_entry_point = gunicorn_options.get('entry_point')
        if gunicorn_entry_point is None:
            if self.major_version >= (6, 2):
                # proxy vs direct now handled by an OpenERP server option
                gunicorn_entry_point = 'openerp:service.wsgi_server.application'
            else:
                gunicorn_entry_point = (
                    'openerp:wsgi.%s.application' % self.gunicorn_entry)

        # gunicorn's main() does not take arguments, that's why we have
        # to resort on hacking sys.argv
        options['initialization'] = (
            "from sys import argv; "
            "argv[1:] = ['%s', "
            "            '-c', '%s.conf.py']") % (
            gunicorn_entry_point, join(self.etc, qualified_name))

        zc.recipe.egg.Scripts(self.buildout, '', options).install()
        self.openerp_installed.append(join(self.bin_dir, qualified_name))

    def _install_openerp_command(self, qualified_name):
        """Install https://launchpad.net/openerp-command)
        """
        logger.warn("Installing openerp-command as %r. This is useful for "
                    "development operations, but not ready to launch "
                    "production instances yet.", qualified_name)

        options = self.options.copy()
        options['scripts'] = 'oe=' + qualified_name
        # can't reuse self.addons here, because the true addons path maybe
        # different depending on addons options, such as subdir
        addons = self.options['options.addons_path'].replace(',', ':')
        initialization = ["import os",
                          "os.environ['OPENERP_ADDONS'] = %r" % addons,
                          '']

        if self.with_devtools:
            initialization.extend((
                    'from anybox.recipe.openerp import devtools',
                    'devtools.load(for_tests=True)',
                    ''))
        options['initialization'] = os.linesep.join(initialization)

        zc.recipe.egg.Scripts(self.buildout, '', options).install()
        self.openerp_installed.append(join(self.bin_dir, qualified_name))

    def _install_cron_worker_startup_script(self, qualified_name):
        """Install the cron worker script.

        This worker script has been introduced in openobject-server, rev 4184
        together with changes in the main code that it requires.
        These changes appeared in nightly build 6.1-20120530-233414.
        The worker script itself does not appear in nightly builds.
        """

        script_src = join(self.openerp_dir, 'openerp-cron-worker')
        if not os.path.isfile(script_src):
            version = self.version_detected
            if ((version.startswith('6.1-2012') and version[4:12] < '20120530')
                or self.version_wanted == '6.1-1'):
                logger.warn(
                    "Can't use openerp-cron-worker with version %s "
                    "You have to run a separate regular OpenERP process "
                    "for cron jobs to be launched.", version)
                return

            logger.info("Cron launcher openerp-cron-worker not found in "
                        "openerp source tree (version %s). "
                        "This is expected with some nightly builds. "
                        "Using the launcher script distributed "
                        "with the recipe.", version)
            script_src = join(os.path.split(__file__)[0], 'openerp-cron-worker')

        options = self.options.copy()
        options['entry-points'] = ('openerp_starter=anybox.recipe.'
                                   'openerp.start_openerp:main')
        options['scripts'] = 'openerp_starter=' + qualified_name
        options['arguments'] = '%r, %r' % (script_src, self.config_path)
        options['dependent-scripts'] = 'false'
        zc.recipe.egg.Scripts(self.buildout, '', options).install()

    def _install_main_startup_script(self):
        """Install the main startup script, usually called ``start_openerp``.

        Uses a derivation to a console script provided by the recipe and
        a tweaked call to a dedicated instance of zc.recipe.eggs:scripts.
        """
        script_name = self.options.get('script_name', 'start_' + self.name)
        startup_delay = float(self.options.get('startup_delay', 0))

        options = self.options.copy()
        options['entry-points'] = ('openerp_starter=anybox.recipe.'
                                   'openerp.start_openerp:main')
        options['scripts'] = 'openerp_starter=' + script_name

        initialization = ['']
        if self.with_devtools:
            initialization.extend((
                    'from anybox.recipe.openerp import devtools',
                    'devtools.load(for_tests=False)',
                    ''))

        if startup_delay:
            initialization.extend(('print("sleeping %s seconds...")' % startup_delay,
                                   'import time',
                                   'time.sleep(%f)' % startup_delay))

        options['initialization'] = os.linesep.join((initialization))

        if self.major_version == (6, 0):
            server_cmd = join('bin', 'openerp-server.py')
        else:
            server_cmd = 'openerp-server'

        options['arguments'] = '%r, %r' % (
            join(self.openerp_dir, server_cmd), self.config_path)
        options['dependent-scripts'] = 'false'
        zc.recipe.egg.Scripts(self.buildout, '', options).install()

        self.script_path = join(self.bin_dir, script_name)
        self.openerp_installed.append(self.script_path)

    def _install_test_script(self):
        """Install the main startup script, usually called ``start_openerp``.

        Uses a derivation to a console script provided by the recipe and
        a tweaked call to a dedicated instance of zc.recipe.eggs:scripts.
        """

        script_name = self.options.get('test_script_name', 'test_' + self.name)

        options = self.options.copy()
        options['entry-points'] = ('openerp_tester=anybox.recipe.'
                                   'openerp.test_openerp:main')
        options['scripts'] = 'openerp_tester=' + script_name

        initialization = ['']
        initialization.extend(('from anybox.recipe.openerp import devtools',
                               'devtools.load(for_tests=True)', ''))

        options['initialization'] = os.linesep.join((initialization))

        if self.major_version == (6, 0):
            server_cmd = join('bin', 'openerp-server.py')
        else:
            server_cmd = 'openerp-server'

        options['arguments'] = '%r, %r, %r' % (
            join(self.openerp_dir, server_cmd), self.config_path,
            self.version_detected)
        options['dependent-scripts'] = 'false'
        zc.recipe.egg.Scripts(self.buildout, '', options).install()

        self.script_path = join(self.bin_dir, script_name)
        self.openerp_installed.append(self.script_path)


    def _install_startup_scripts(self):
        """install startup and control scripts.
        """

        self._install_main_startup_script()

        if self.with_openerp_command:
            self._install_openerp_command(
                self.options.get('openerp_command_name',
                                 '%s_command' % self.name))

        if self.with_devtools:
            self._install_test_script()

        if self.with_gunicorn:
            qualified_name = self.options.get('gunicorn_script_name',
                                              'gunicorn_%s' % self.name)
            self._create_gunicorn_conf(qualified_name)
            self._install_gunicorn_startup_script(qualified_name)

            qualified_name = self.options.get('cron_worker_script_name',
                                              'cron_worker_%s' % self.name)
            self._install_cron_worker_startup_script(qualified_name)

    def _60_fix_root_path(self):
        """Correction of root path for OpenERP 6.0 pure python install"""

        if 'options.root_path' not in self.options:
            self.options['options.root_path'] = join(self.openerp_dir, 'bin')

    def _60_default_addons_path(self):
        """Set the correct default addons path for OpenERP 6.0."""
        self.options['options.addons_path'] = join(self.openerp_dir,
                                                   'bin', 'addons')
