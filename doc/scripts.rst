Odoo Scripts
============

The server recipe actually includes a general engine to install Python
code that needs access to the Odoo API and build
configuration-aware executables.

As usual, it tries and do so by bridging the standard Python packaging
practice (setuptools-style console scripts, as in
``zc.recipe.egg:scripts``) and Odoo specificities.

We call such scripts *Odoo scripts* to distinguish them among the
more general concept of console scripts.

.. warning:: Odoo scripts are currently supported for versions ≥ 6.1 only.


Use cases
~~~~~~~~~

Odoo scripts can do great in situations where an RPC script might
not be powerful enough or not practical. Some examples:

* specific batch jobs, especially for large databases (you get to
  control the transaction).
* introspection tools.
* general-purposes test launchers that don't have any knowledge of
  Odoo specifics, such as ``nose``. See :ref:`command_line_options`
  for details about that.
* Enhanced Python consoles, like ``IPython`` or ``bpython``.
  See :ref:`interactive_consoles`.

Odoo vs RPC scripts for administrative tasks
--------------------------------------------

There are several Python distributions that wrap the Odoo RPC APIs
for easy use within Python code.

Using an RPC script for administrative tasks usually leads to
wrap it in a shell script, with the admin password in clear text.

In this author's experience of applicative maintainance,
this always turns to be an
easy source of breakage that may look to be trivial at first sight but
has actually two nasty properties : it may stay unnoticed for a while,
and it lies at the interface between responsibilities.

In case of password change, the persons who can do it
in the database and in the system usually differ, and may not
communicate on a regular basis. In enterprise hosting environments,
you may have to explain stuff to several project managers with
different responsabilities, go through crisis management meetings,
etc. Who wants to waste hours of their life interacting with people
under stress to try and persuade them that it's only a matter of
changing an obscure password ?


Odoo scripts vs Odoo cron jobs
---------------------------------

Because they are part of addons, Odoo cron jobs also have full
unrestricted access to the internal API, and obviously don't suffer
from the password plague.

Some ideas to make a choice:

* who should control, schedule and tune execution (a system administrator or
  a functional admin)
* which one the script author finds easiest to write for
* reuse and distribution issues : Odoo scripts are in Python
  distributions, cron jobs are in addons.
* Odoo scripts must implement their own transaction control,
  whereas cron jobs don't bother about it but rely on the framework's
  decisions.

Perhaps, the best is not to choose : put the bulk of the logic in some
technical addon, it's easy to rewrap it in an Odoo script and as a
cron job.


Declaring Odoo Scripts
~~~~~~~~~~~~~~~~~~~~~~
There are several cases, depending on the script authors
intentions. Script authors should therefore state clearly in their
documentation how to declare them.

Assume to fix ideas there is a Python distribution ``my.script``
that declares a console script entry point named ``my_script`` in its
``setup.py``::

      entry_points="""

      [console_scripts]
      my_script = my.script.main:run
      """

The first thing to do is to require that distribution using the
``eggs`` option::

  [my-openerp]
  (...)
  eggs = my.script

:ref:`How that distribution can be made available to buildout
<making_available>` is a different question.

Bare declararations
-------------------
The following configuration::

  [openerp-one]
  (...)
  openerp_scripts = my_script

Produces an executable ``bin/my_script-openerp-one``, that can import
Odoo server and addons code, and in which the Odoo configuration
related to the appropriate buildout part (here, ``openerp-one``) is
loaded in the standard ``openerp.tools.config``, for use in the
script. The script has to take care of all database management operations.

Optionally, it's possible to specify the name of the produced script::

  [openerp-one]
  (...)
  openerp_scripts = my_script=wished_name

That would build the script as ``bin/wished_name``.

This is good
enough for scripts that'd take care of many bootstrapping details, but
there is a more integrated way that script authors should be aware of:
the special ``session`` argument.

.. _arguments_session:

Arguments and session
---------------------
.. note:: new in version 1.7.0

An ``arguments`` parameter, similar to the one of
``zc.recipe.egg:scripts`` can be specified::

  [openerp-two]
  (...)
  openerp_scripts = my_script arguments=2,3

This is a raw string that will be used as the string of arguments for
the callable specified in the entry point, as in ``main(2,3)`` in that
example.

There is a special argument: ``session``, which is an object provided
by the recipe to expose Odoo API in a convenient manner for script
authors. Check
:py:class:`anybox.recipe.openerp.runtime.session.Session` to learn
what can be done with it.

Scripts written for these ``session`` objects must be declared as such::

 [openerp-two]
 (...)
 openerp_scripts = my_script arguments=session

.. _command_line_options:

Command-line options
--------------------

In some cases, it is useful to do some operations, such as preloading
a database, before actual running of the script. This is intended for
scripts which have no special knowledge of Odoo but may in turn
call some code meant for Odoo, that'd need some preparations to
already have been performed.

The main use-case is unit tests launchers.

For these, the ``command-line-options`` modifier tells the recipe to
produce an executable that will implement some additional command-line
options parsing and perform some actions accordingly. On the
command-line ``--`` is used as a separator between those additional
options and the regular arguments expected by the script.

Example::

  [openerp-three]
  (...)
  openerp_scripts = nosetests command-line-options=-d

This produces a ``bin/nosetests_openerp-three``, which you can use
like this::

  bin/nosetests_openerp-three -d mydb -- [NOSE REGULAR OPTIONS & ARGUMENTS]

Currently available command-line-options:

:-d DB_NAME: preload the specified database

.. _openerp_log_level:

Odoo log level
--------------
This is mostly meant for scripts with the ``command-line-options=-d``
modifier.

In some cases, one is not interested in the logs during the Odoo
database load. The typical use-case this has been made for is the
``sphinx-build`` script, where any warning from Odoo would just
make it harder to stop actual documentation warnings, or to limit the
output of test launcher before actual testing begins.

The ``openerp_log_level`` modifier lets you specify the log level for
the ``openerp`` logger, at the very start of the script, before any
database loading is performed.

In the case of ``sphinx-build`` this has the advantage of not
affecting the root logger nor the Sphinx dedicated ones.

Of course, the actual script can override that setting once it really
starts, in which case the modifier is really only about the loading sequence.

.. _interactive_consoles:

Interactive Consoles
~~~~~~~~~~~~~~~~~~~~

One particularly interesting use of `openerp_scripts` is to enable the use of
enhanced Python interactive interpreters, like `IPython <http://ipython.org>`_
or `bPython <http://bpython-interpreter.org>`_::

  [buildout]
  parts = odoo

  [odoo]
  version = git http://github.com/odoo/odoo.git odoo 8.0 depth=1
  recipe = anybox.recipe.odoo:server
  eggs =
      ipython
      bpython
  openerp_scripts =
      ipython arguments=user_ns=dict(session=session)
      bpython arguments=locals_=dict(session=session)

The example ``buildout.cfg`` above will generate both a ``ipython_odoo`` and a
``bpython_odoo`` scripts in the ``bin`` directory, which can be used like the
Python interpreter generated by :ref:`interpreter_name`, where the ``session``
object is available for interacting with your odoo application and database.

Keep in mind that ``bpython`` requires more system dependencies installed than
plain ``odoo``.

Note that Odoo forbids using the ``postgres`` user to connect to the database.
But in some containerized environments (Docker), using ``postgres`` can be
both safe and handy. In such case you would need to patch the Odoo server as
of today. But for the interactives sessions of this buildout recipe, you can
set the environment variable ENABLE_POSTGRES_USER=1 before opening the console
to disable the default ``check_postgres_user()`` guard and enable the postgres
user.

Writing Odoo Scripts
~~~~~~~~~~~~~~~~~~~~

Script authors have to:

* write their script as a callable within a setuptools
  distribution. Usually that'd be a function ``my_run`` at toplevel of
  a ``my/script/main.py`` file
* declare that callable in ``setup.py`` like this::

      entry_points="""

      [console_scripts]
      my_script = my.script.main:my_run
      """
* (recommended) use the
  :py:class:`anybox.recipe.openerp.runtime.session.Session` API. For
  that, let your callable accept a ``session`` argument, and tell
  users to :ref:`pass it in their buildout configuration <arguments_session>`.

* write the actual script! Here's a silly example, that outputs the
  total of users in the database::

       from argparse import ArgumentsParser

       def my_run(session):
           # command-line arguments handling is up to the script
           parser = ArgumentsParser()
           parser.add_argument('-d', '--database',
                               help="Database to work on", required=True)
           arguments = parser.parse_args()

           # loading the DB
           session.open(arguments.database)

           # using the models
           users = session.registry('res.users').search(
               session.cr, session.uid, [])

           print("There are %d users in database %r" % (
               len(users), arguments.database))

           # Transaction control is up to the script
           session.rollback()  # we didn't write anything, but one never knows

.. _making_available:

Making the distribution available
---------------------------------

In order to be used by the recipe, the distribution that holds the
script code has to be *required* with the ``eggs`` option. But how can
buildout retrieve it ? There's nothing specific to the Odoo recipe
about that, it works in the exact same way as for the standard
``zc.recipe.eggs`` recipe.

We list here some possibilities, as a convenience for readers without
a more general buildout experience.

* provide it locally and tell buildout to "develop" it::

      [buildout]
      develop = my_script_distribution_path

  paths are interpreted relative to the buildout directory, but may be
  absolute.

* put it on the `Python Package Index <https://pypi.python.org>`_
* put it in a private index and use the ``index`` main buildout option
* prebuild an egg and put it in the eggs directory (can be shared
  between several buildouts).
* put a source distribution (tarball) or an egg on some HTTP server,
  and use the ``find-links`` global buildout option.
* grab it and develop it from an external VCS, using the
  `gp.vcsdevelop <https://pypi.python.org/gp.vcsdevelop>`_ buildout extension.
* use one of the other VCS-oriented buildout extensions (such as
  `mr.developer <https://pypi.python.org/pypi/mr.developer/>`_

.. note:: the releasing features (freeze, extract) of the recipe are
          aware of ``gp.vcsdevelop`` and will control the revision it
          uses. There's no such support of ``mr.developer`` right now.

.. _upgrade_scripts:

Upgrade scripts
~~~~~~~~~~~~~~~
.. note:: new in version 1.8.0

The recipe provides a toolkit for database management, including
upgrade scripts generation, to fulfill two seemingly contradictory goals:

* **Uniformity**: all buildout-driven
  installations have upgrade scripts with the same command-line
  arguments, similar output, and all the costly details that matter
  for industrialisation, or simply execution by a pure system
  administrator, such as success log line, proper status code, already
  taken care of. Even for one-shot delicate upgrades, repetition is
  paramount (early detection of problems through rehearsals).
* **Flexibility**: "one-size-fits all" is precisely what the recipe is
  meant to avoid. In the sensitive case of upgrades, we know that an
  guess-based approach that would work in 90% of cases is not good enough.

To accomodate these two needs, the installation-dependent
flexibility is given back to the user (a
project maintainer in that case) by letting her write the actual
upgrade logic in the simplest way possible. The recipe rewraps it and
produces the actual executable, with its command-line parsing, etc.

Project maintainers have to produce a callable using the
high-level methods of
:py:class:`anybox.recipe.openerp.runtime.session.Session`. Here's an
example::

   def run_upgrade(session, logger):
       db_version = session.db_version  # this is the state after
                                        # latest upgrade
       if db_version < '1.0':
          session.update_modules(['account_account'])
       else:
          logger.warn("Not upgrading account_account, as we know it "
                      "to be currently a problem with our setup. ")
       session.update_modules(['crm', 'sales'])

No need to set ``db_version``, nor to commit: the recipe will do it
for you in case of success (see below)

Such callables (source file and name) can be declared in the
buildout configuration with the ``upgrade_script`` option::

  upgrade_script = my_upgrade.py run_upgrade

The default is ``upgrade.py run``. The path is interpreted relative to
the buildout directory.

If the specified source file is not found, the recipe will initialize it
with the simplest possible one : update of all modules. That is
expected to work 90% of the time. The package manager can then modify
it according to needs, and maybe track it in version control.

.. note:: about versions

          the ``db_version`` settable property is meant to be really
          global for this precise project. The idea is that anything
          depending only on a module's version number should be done
          in that module's migration scripts (pre or post).

          you're supposed to provide and maintain a "package version" in a
          ``VERSION.txt`` file at the root of the buildout (the recipe
          will warn you if it's missing). The recipe will use it to set
          ``db_version`` at the end of the process.

In truth, upgrade scripts are nothing but Odoo scripts, with the
entry point console script being provided by the recipe itself, and
in turn relaying to that user-level callable.
See :py:mod:`anybox.recipe.openerp.runtime.upgrade` for more details
on how it works.

Usage for instance creation
---------------------------
For projects with a fixed number of modules to install at a given
point of code history, upgrade scripts can be used to install a
fresh database::

  def upgrade(session, logger):
      """Create or upgrade an instance or my_project."""
      if session.is_initialization:
          logger.info("Installing modules on fresh database")
          session.install_modules(['my_module'])
          return

      # now upgrade logic

Not having a command-line argument for modules ot install in
the resulting script *is a strength*.
It means that CI robots, deployment tools
and the like will be able to install it with zero additional
configuration.

The default script produced by the recipe also detects initializations
and logs information on how to customize::

    2013-10-14 17:16:17,785 WARNING  Usage of upgrade script for initialization detected. You should consider customizing the present upgrade script to add modules install commands. The present script is at : /home/gracinet/openerp/recipe/testing-buildouts/upgrade.py (byte-compiled form)
    2013-10-14 17:16:17,786 INFO  Initialization successful. Total time: 22 seconds.


.. note:: the ``is_initialization`` attribute is new in version 1.8.1


Options of the produced executable upgrade script
-------------------------------------------------

Command-line parsing is done with `argparse
<http://docs.python.org/2/library/argparse.html>`_. If you have any doubt,
use ``--help`` with the version you have. Here's the current state::

  $ bin/upgrade_openerp -h
  usage: upgrade_openerp [-h] [--log-file LOG_FILE] [--log-level LOG_LEVEL]
                         [--console-log-level CONSOLE_LOG_LEVEL] [-q]
                         [-d DB_NAME]

  optional arguments:
    -h, --help            show this help message and exit
    --log-file LOG_FILE   File to log sub-operations to, relative to the current
                          working directory, supports homedir expansion ('~' on
                          POSIX systems). (default: upgrade.log)
    --log-level LOG_LEVEL
                          Main Odoo logging level. Does not affect the
                          logging from the main upgrade script itself. (default:
                          info)
    --console-log-level CONSOLE_LOG_LEVEL
                          Level for the upgrade process console logging. This is
                          for the main upgrade script itself meaning that
                          usually only major steps should be logged (default:
                          info)
    -q, --quiet           Suppress console output from the main upgrade script
                          (lower level stages can still write) (default: False)
    -d DB_NAME, --db-name DB_NAME
                          Database name. If ommitted, the general default values
                          from Odoo config file or libpq will apply.
    --init-load-demo-data
                          Demo data will be loaded with module installations if
                          and only if this modifier is specified (default:
                          False)


Sample output
-------------

Here's the output of a run of the default upgrade script::

  $ bin/upgrade_openerp -d testrecipe
  Starting upgrade, logging details to /home/gracinet/openerp/recipe/testing-buildouts/upgrade.log at level INFO, and major steps to console at level INFO

  2013-09-21 18:53:23,471 WARNING  Expected package version file '/home/gracinet/openerp/recipe/testing-buildouts/VERSION.txt' does not exist. version won't be set in database at the end of upgrade. Consider including such a version file in your project *before* version dependent logic is actually needed.
  2013-09-21 18:53:23,471 INFO  Database 'testrecipe' loaded. Actual upgrade begins.
  2013-09-21 18:53:23,471 INFO  Default upgrade procedure : updating all modules.
  2013-09-21 18:53:54,029 INFO  Upgrade successful. Total time: 32 seconds.

The same with a version file::

  $ bin/upgrade_openerp -d testrecipe
  Starting upgrade, logging details to /home/gracinet/openerp/recipe/testing-buildouts/upgrade.log at level INFO, and major steps to console at level INFO

  2013-09-22 19:23:17,908 INFO  Read package version: 6.6.6-final from /home/gracinet/openerp/recipe/testing-buildouts/VERSION.txt
  2013-09-22 19:23:17,908 INFO  Database 'testrecipe' loaded. Actual upgrade begins.
  2013-09-22 19:23:17,909 INFO  Default upgrade procedure : updating all modules.
  2013-09-22 19:23:48,626 INFO  setting version 6.6.6-final in database
  2013-09-22 19:23:48,635 INFO  Upgrade successful. Total time: 32 seconds.


Startup scripts
~~~~~~~~~~~~~~~
The familiar ``start_openerp``, and its less pervasing siblings
(``gunicorn_openerp``, ``test_openerp``, …) are also special cases of
Odoo scripts.

What is special with them amounts to the following:

* the entry points are declared by the recipe itself, not by a
  third-party Python distribution.
* the recipe includes some initialization code in the final
  executable, in a way that the configuration presently could not allow.
* often, they don't use the session objects, but rewrap instead the mainline
  startup script.

In particular, you can control the names of the startup scripts with
the ``openerp_scripts`` option. For instance, to
replace ``bin/start_openerp`` with ``bin/oerp``, just do::

  [openerp]
  (...)
  openerp_scripts = openerp_starter=oerp

List of internal entry points
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Here's the list of currently available internal entry points.

:openerp_starter: main Odoo startup script (dynamically added
                  behing the scenes by the recipe)
:openerp_tester: uniform script to start Odoo, launch all tests and
                 exit. This can be achieved with the main startup
                 scripts, but options differ among Odoo versions.
                 (also dynamically added behind the scenes).
:openerp_upgrader: entry point for the upgrade script
:openerp_cron_worker: entry point for the cron worker script that gets
                      built for gunicorn setups.
:oe: entry point declared by ``openerp-command`` and used by the recipe.
:gunicorn: entry point declared by ``gunicorn`` and used by the recipe.

.. note:: For these entry points, the ``command-line-options`` and
          ``arguments`` modifiers have no effect.
