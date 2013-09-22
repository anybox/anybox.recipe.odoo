OpenERP Scripts
===============

The server recipe actually includes a general engine to install Python
code that needs access to the OpenERP API and build
configuration-aware executables.

As usual, it tries and do so by bridging the standard Python packaging
practice (setuptools-style console scripts, as in
``zc.recipe.egg:scripts``) and OpenERP specificities.

We call such scripts *OpenERP scripts* to distinguish them among the
more general concept of console scripts.


Use cases
~~~~~~~~~

OpenERP scripts can do great in situations where an RPC script might
not be powerful enough or not practical. Some examples:

* specific batch jobs, especially for large databases (you get to
  control the transaction).
* introspection tools.
* general-purposes test launchers that don't have any knowledge of
  OpenERP specifics, such as ``nose``. See :ref:`command_line_options`
  for details about that.

OpenERP vs RPC scripts for administrative tasks
-----------------------------------------------

There are several Python distributions that wrap the OpenERP RPC APIs
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


OpenERP scripts vs Openerp cron jobs
------------------------------------

Because they are part of addons, OpenERP cron jobs also have full
unrestricted access to the internal API, and obviously don't suffer
from the password plague.

Some ideas to make a choice:

* who should control, schedule and tune execution (a system administrator or
  a functional admin)
* which one the script author finds easiest to write for
* reuse and distribution issues : OpenERP scripts are in Python
  distributions, cron jobs are in addons.
* OpenERP scripts must implement their own transaction control,
  whereas cron jobs don't bother about it but rely on the framework's
  decisions.

Perhaps, the best is not to choose : put the bulk of the logic in some
technical addon, it's easy to rewrap it in an OpenERP script and as a
cron job.


Declaring OpenERP Scripts
~~~~~~~~~~~~~~~~~~~~~~~~~
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
OpenERP server and addons code, and in which the OpenERP configuration
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
An ``arguments`` parameter, similar to the one of
``zc.recipe.egg:scripts`` can be specified::

  [openerp-two]
  (...)
  openerp_scripts = my_script arguments=2,3

This is a raw string that will be used as the string of arguments for
the callable specified in the entry point, as in ``main(2,3)`` in that
example.

There is a special argument: ``session``, which is an object provided
by the recipe to expose OpenERP API in a convenient manner for script
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
scripts which have no special knowledge of OpenERP but may in turn
call some code meant for OpenERP, that'd need some preparations to
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

Writing OpenERP Scripts
~~~~~~~~~~~~~~~~~~~~~~~

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
buildout retrieve it ? There's nothing specific to the OpenERP recipe
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

Such callables (source file and name) can be declared in the
buildout configuration with the ``upgrade_script`` option::

  upgrade_script = my_upgrade.py run_upgrade

The default is ``upgrade.py run``. The path is interpreted relative to
the buildout directory.

If the specified source file is not found, the recipe will initialize it
with the simplest possible one : update of all modules. That is
expected to work 90% of the time. The package manager can then modify
it according to needs, and maybe track it in version control.

In truth, upgrade scripts are nothing but OpenERP scripts, with the
entry point console script being provided by the recipe itself, and
in turn relaying to that user-level callable.
See :py:mod:`anybox.recipe.openerp.runtime.upgrade` for more details
on how it works.


Startup scripts
~~~~~~~~~~~~~~~
The familiar ``start_openerp``, and its less pervasing siblings
(``gunicorn_openerp``, ``test_openerp``, …) are also special cases of
OpenERP scripts.

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

:openerp_starter: main OpenERP startup script (dynamically added
                  behing the scenes by the recipe)
:openerp_tester: uniform script to start OpenERP, launch all tests and
                 exit. This can be achieved with the main startup
                 scripts, but options differ among OpenERP versions.
                 (also dynamically added behind the scenes).
:openerp_upgrader: entry point for the upgrade script
:openerp_cron_worker: entry point for the cron worker script that gets
                      built for gunicorn setups.
:oe: entry point declared by ``openerp-command`` and used by the recipe.
:gunicorn: entry point declared by ``gunicorn`` and used by the recipe.

.. note:: For these entry points, the ``command-line-options`` and
          ``arguments`` modifiers have no effect.
