OpenERP Scripts
===============

The server recipe actually includes a general engine to install Python
code that needs access to the OpenERP API and build
configuration-aware executables.

As usual, it tries and do so by bridging the standard Python packaging
practice (setuptools-style console scripts, as in
``zc.recipe.egg:scripts``) and OpenERP specificities.

Declaring OpenERP Scripts
~~~~~~~~~~~~~~~~~~~~~~~~~
There are several cases, depending on the script authors
intentions. Script authors should therefore state clearly in their
documentation how to use them.

Assume to fix ideas there is a Python distribution ``my.script``
that declares a console script entry point named ``my_script``.

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
       db_version = session.db_version
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
