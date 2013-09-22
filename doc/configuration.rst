Configuration reference
=======================

This is a `Buildout <https://github.com/buildout/buildout>`_ recipe that can
download, install and configure one or several OpenERP servers, web clients,
gtk clients and addons modules, from official or custom sources, or any bzr,
hg, git or svn repositories.  It currently supports versions 6.0, 6.1 and 7.0,
with gunicorn deployment and an additional cron worker. It works under Linux
and MacOs. It might work under Windows but it is untested.

A "Buildout recipe" is the engine behind a Buildout "part". A "buildout part"
is a part of a larger application built with the Buildout sandbox build system.
Using Buildout is harmless for your system because it is entirely
self-contained in a single directory: just delete the directory and the
buildout is gone. You never have to use administrative rights, except for
build dependencies.

.. _buildout_conf_parts:

The buildout configuration file and parts
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
The intents of this seciton is to highlights a few facts that we've
found especially useful. People should refer to the reference zc.buildout
documentation available online.

Buildout configuration files are written almost in INI format, and
always start with a ``buildout`` section::

  [buildout]
  parts = openerp

The ``parts`` option specifies which parts to install by default if
one runs ``bin/buildout`` with no explicit ``install`` directive.

Parts directly correspond to sections of the configuration file, and
must specify the recipe that's to be used::

  [openerp]
  recipe = anybox.recipe.openerp:server

Command line
------------
The configuration file can be specified from the command line::

  bin/buildout -c buildout.local.cfg

Recipe options can be overridden from the command-line::

  bin/buildout -c buildout.local.cfg openerp:clean=True openerp:xmlrpc_port=8169

Parts that are not listed in the ``buildout`` configuration section
can be explicitely installed::

  bin/buildout install openerp funkload static-analysis

.. _extends:

Inheritance
-----------

A buildout configuration file can reference another one and change
some options (note the ``+=`` notation that's not part of the INI format)::

  [buildout]
  extends = buildout.base.cfg

  [openerp]
  eggs += nose
          coverage
  with_devtools = True

These extensions can be chained. This allows in particular project maintainers
to separate the configuration options that are considered to be part
of the project from those that depend on the server environment
(ports, database hosts…)

Default configuration
---------------------

If available, the settings from ``$HOME/.buildout/default.cfg`` always
apply, as if it where the default value of the :ref:`extends <extends>` option.

This is commonly used with the ``eggs-directory`` and
:ref:`openerp-downloads-directory` options, because these amount to create a
user-level cache.

Finally, you may also use :ref:`extends <extends>` in ``default.cfg`` to point
to a system-wide configuration file (useful to enforce
policies at the organization or physical site level, such as local
index servers, mirrors, etc.).

OpenERP recipes
~~~~~~~~~~~~~~~

There are three different recipes bundled with
``anybox.recipe.openerp``. The option line to put in your part (see
:ref:`buildout_conf_parts`) is the following.

For the server::

    recipe = anybox.recipe.openerp:server

For the web client::

    recipe = anybox.recipe.openerp:webclient

For the gtk client::

    recipe = anybox.recipe.openerp:gtkclient

.. note:: from OpenERP 7.0 onwards, the web and gtk clients aren't
          that useful anymore.

Default options from zc.recipe.egg
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

This recipe reuses the *zc.recipe.egg:scripts* recipe, so the options
are the same (*eggs*, *interpreter*, etc.), with some important
changes.

Consult the documentation here http://pypi.python.org/pypi/zc.recipe.egg

The main useful ones are below:

eggs
----

Starting from version 0.16 of the recipe, you don't need to put anything in
this option by default : the recipe is supposed to add all needed
dependencies for OpenERP by itself, but you have to specify additional
eggs needed by addons, or just useful ones::

    eggs =
        ipython
        python-ldap
        openobject-library

scripts
-------
.. note:: This option is useful for general purpose scripts
          only. For scripts related to OpenERP, see
          :doc:`/scripts`, and the :ref:`openerp_scripts` option.

The behaviour of this option is slightly modified :
by default, no script other than those directly related to OpenERP are
generated, but you may specify some explicitely, with the same semantics as the
normal behaviour (we simply set an empty default value, which means to not
produce scripts)::

        scripts =
            change_tz

In the current state, beware to *not* require the same script in different
parts or rename them. See
https://bugs.launchpad.net/anybox.recipe.openerp/+bug/1020967 for
details.

interpreter
-----------
With the ``gtkclient`` and ``webclient`` recipes,
this is the default `interpreter` option of `zc.recipe.egg` that
specifies the name of the Python interpreter that shoud be included in
the``bin`` directory of the buildout::

    interpreter = erp_python

With the ``server`` recipe, the ``interpreter`` option will be ignored,
because this recipe always creates an interpreter with preloaded objects to
bootstrap openerp. Check :ref:`interpreter_name` for more details.


Specific options
~~~~~~~~~~~~~~~~

The recipe also adds a few specific options:

.. _version:

version
-------

Specifies the OpenERP version to use. It can be:

The **version number** of an official OpenERP (server, web client or gtk client)::

  version = 6.0.3

A **custom download**::

  version = url http://example.com/openerp.tar.gz

An absolute or a relative **path**::

  version = path /my/path/to/a/custom/openerp

A custom **bzr, hg, git or svn** branch or repository. The syntax is the same
as the :ref:`addons` option::

  version = bzr lp:openobject-server/6.1 openerp61 last:1

A **nightly** build::

  version = nightly 6.1 20120814-233345

or (dangerously unpinned version)::

  version = nightly 6.1 latest

or even more dangerous::

  version = nightly trunk latest

.. _addons:

addons
------

Specifies additional OpenERP addons, either a local path or a repository.

Example::

  addons = local ../some/relative/path/for/custom_addons/
           local /some/other/absolute/path/for/custom_addons
           bzr lp:openobject-addons/trunk/    addons0 last:1
           hg  http://example.com/some_addons addons1 default
           git http://example.com/some_addons addons2 master
           svn http://example.com/some_addons addons3 head
           bzr lp:openerp-web/trunk/ openerp-web last:1 subdir=addons

When using ``local`` paths you can either specify a directory holding
addons, or a single addon. In that latter case, it will be actually
placed one directory below.

.. warning::

   Never name one of these addons directory simply ``addons``. It
   leads to obscure and blocking install errors for addons in other
   directories, claiming that some files don't exist while they do.

For remote repositories, the syntax is:

    ``TYPE  URL  DESTINATION  REVISION  [OPTIONS]``

with the following semantics:

:TYPE: one of ``bzr``, ``hg``, ``git`` or ``svn``
:URL: is any URL scheme supported by the versionning tool
:DESTINATION: is the local directory that will be created (relative or absolute)
:REVISION: is any version specification supported (revision, tag, etc.)
:OPTIONS: each one takes the form ``name=value``. No whitespace is
          allowed inside an option, and no escaping is
          implemented.

Repositories are updated on each build according to the specified
revision. You must be careful with the revision specification.

Buildout offline mode is supported. In that case, update to the
specified revision is performed, if the VCS allows it (Subversion does
not).

The ``subdir`` addons option
````````````````````````````

The ``subdir`` option, if used, makes the recipe use the given
subdirectory of the repository as the addons directory.
A very common example is the line for standard web addons from bzr::

   bzr lp:openerp-web/7.0 openerp-web last:1 subdir=addons

The ``bzr-init`` addons option
``````````````````````````````

**'bzr-init'** defines the way the bzr branch
is initialized for addons or server declared with a bzr
repository path.

Possible values:

:branch (default):  Working copy initialized with the command
                    ``bzr branch url ...``

:stacked-branch:  Working copy initialized with the command
                  ``bzr branch --stacked url ...``
:lightweight-checkout: Working copy initialized with the command
                       ``bzr checkout --lightweight url ...``

.. _revisions:

revisions
---------

This option allows to further precise what has been specified through
the  :ref:`addons` and :ref:`version` options by fixing VCS revisions.

The main use-case it to apply it in an :ref:`extension buildout
configuration file <extends>`::

   [buildout]
   extends = base.cfg

   [openerp]
   revisions = 4320  ; main software
               addons-openerp 7109

As you can see in that example, the first token is the target
filesystem path, as in the :ref:`addons` option, the second one is the
revision, except in the case of the main software (if VCS based), for
which there's no filesystem path.

Some interesting use-cases:

* temporary fixing some revision in cas of upstream regression with no
  impact on your main development configuration (no risk to commit an
  unwanted freeze if the main configuration is itself versionned).
* freezing satisfactory revisions in a release process (the recipe can
  do that automatically for you, see ``freeze-to`` option below).

.. _clean:

clean
-----

If set to true, this option will clean remove python object files from
the main server part and addons before any update or install, and
perform relevant VCS idea of "clean, purge".

.. warning:: developers can lose their uncommitted work with this option.

             This option is not meant for developer setups, rather for
             deployment and continuous integration. To avoid making a
             dedicated buildout configuration for you CI bot, just add
             it on the command-line.

Note that tarball downloads get re-extracted afresh in any case.

.. _openerp_scripts:

openerp_scripts
---------------

This option lets you install console scripts provided by any of the loaded eggs,
so that they can access to OpenERP internals and load databases.

Here we describe the format of the option only.
For explanation about what it means and how to use it, please refer to
:doc:`/scripts`.

The option is multiline. Each line specifies exactly one
script, and must respect the following format:

  ``ENTRY_POINT_NAME[=WISHED_SCRIPT_NAME] [MODIFIER [MODIFIER […]]]``

Each modifier takes the ``MODIFIER_NAME=MODIFIER_VALUE`` form.
No whitespace is allowed in modifiers, entry point, nor produced script names.

Here's the list of currently available modifiers, with links inside :doc:`the
dedicated chapter about OpenERP scripts </scripts>`).

:command-line-options: :ref:`command_line_options`
:arguments: :ref:`arguments_session`

Full example::

  openerp_scripts = my_script arguments=session
                    my_other_script=actual-script-name arguments=3,session
                    nosetests=nosetests command-line-options=-d

.. _script_name:

script_name
-----------

.. warning:: as of version 1.7.0, this option is deprecated because of its
             redundancy with :ref:`openerp_scripts`.

OpenERP startup scripts are created in the `bin` directory. By default the name is:
start_<part_name>, so you can have several startup scripts for each part if you
configure several OpenERP servers or clients. You can pass additional typical
arguments to the server via the startup script, such as -i or -u options.

You can choose another name for the script by using the *script_name*
option ::

    script_name = start_erp

.. _upgrade_script_name:

upgrade_script_name
-------------------

This option lets you specify the wished name for the upgrade script.
The default value is ``upgrade_<part_name>``.

.. note:: new in version 1.8.0.

          We are actually not sure to keep that option, since it's
          redundant with :ref:`openerp_scripts`.

.. _upgrade_script:

upgrade_script
--------------

This option lets you specify a source (``.py``) file and a callable
defined in that file to perform database upgrades. The default value
is::

  upgrade_script = upgrade.py run

If the specified source file doest not exist, the recipe will
initialize it with a simple and meaningful sample content, consistent
with the default value above.

If you want *not* to have an upgrade script, just override this option
with a blank value::

  upgrade_script =

See the full :ref:`upgrade_scripts` documentation to learn more
about upgrade scripts.

.. note:: new in version 1.8.0

.. _interpreter_name:

interpreter_name
----------------

The recipe will automatically create a python interpreter with a
``session`` object that can bootstrap OpenERP with a database right
away. You can use that for interactive sessions or to launch a script::

    $ bin/python_openerp
    To start the OpenERP working session, just do:
       session.open()
    or
       session.open(db=DATABASE_NAME)
    Then you can issue commands such as
       session.registry('res.users').browse(session.cr, 1, 1)

    >>>

The interpreter name is  ``python_<part_name>`` by default; but it can
be explicitely set like this::

    interpreter_name = my_py

If you want *not* to have the interpreter, juste do

    interpreter_name =

If you want to wrap a python script with such session objects, read
:doc:`/scripts` and especially :ref:`arguments_session`.
See also :ref:`openerp_scripts`.

.. note:: this facility is new in version 1.6.0, and tested with
          OpenERP 7 only for now.

.. _startup_delay:

startup_delay
-------------

Specifies a delay in seconds to wait before actually launching OpenERP. This
option was a preliminary hack to support both gunicorn instance and a legacy
instance.  The Gunicorn startup script (see below) itself is not affected by
this setting ::

    startup_delay = 3

.. _with_devtools:

with_devtools
-------------
Allows to load development and install useful devlopment and testing
tools, notably the following scripts:

* ``test_openerp``: a uniform test launcher for all supported
  versions. See test_script_name option below for details.
* ``openerp_command``: see openerp_command_name option below for
  details. Not installed for OpenERP major versions less than or equal to 6.1.

This option is False by default, hence it's activated this way::

    with_devtools = true

It will also add some dependencies that are typical to development
setups (tests related packages etc.) and automatically load where
needed helpers, such as `anybox.testing.datetime
<http://pypi.python.org/pypi/anybox.testing.datetime>`_ (allows to
cheat with system time).

.. _test_script_name:

test_script_name
----------------
.. warning:: as of version 1.7.0, this option is deprecated because of its
             redundancy with :ref:`openerp_scripts`.

If the ``with_devtools`` is set to True, the recipe will create a
test script, which is named by default ``test_<part_name>``. You may
override the name in the configuration as in the following example::

  test_script_name = test_erp

The test script takes the same arguments as the regular startup
script::

  bin/test_openerp --help
  bin/test_openerp -d test_db -i purchase,sale

At the time of this writing, all this script does compared to the
regular startup script is to bring uniformity across OpenERP versions
by tweaking options internally.

.. _base_url:

base_url
--------

URL from which to download official and nightly versions
(assuming the archive filenames are constistent with those in
OpenERP download server). This is a basic mirroring capability::

    base_url = http://download.example.com/openerp/

.. _openerp-downloads-directory:

openerp-downloads-directory
---------------------------

Allows to share OpenERP downloads among several buildouts. You should put this
option in your ``~/.buildout/default.cfg`` file.  It specifies the destination
download directory for OpenERP archives. The path may be absolute or relative
to the buildout directory.

Example::

    [buildout]
    openerp-downloads-directory = /home/user/.buildout/openerp-downloads

.. _gunicorn:

gunicorn
--------

Gunicorn integration is only supported on OpenERP >= 6.1.
Any value of this option makes the recipe generate a script to start
OpenERP with Gunicorn and (*new in version 1.1*) a dedicated script to
handle cron jobs.

For OpenERP 6.1, the only accepted values are ``direct`` and
``proxied``. Any value is suitable for OpenERP >= 7

Proxied mode
````````````
For OpenERP 6.1, a special value of the ``gunicorn`` option is to be
used if you plan to run Gunicorn behind a reverse proxy::

    gunicorn = proxied

This behaviour has been kept for OpenERP >= 7 to keep
backwards compatibility, but the option is now superseded by the
general ``proxy_mode`` option of the server. In the buildout context,
that'd be::

    options.proxy_mode = True


Gunicorn options
````````````````

Gunicorn-specific options are to be specified with the ``gunicorn.``
prefix and will end up in the the Gunicorn python configuration file
``etc/gunicorn_<part_name>.conf.py``, such as::

  gunicorn.workers = 8

If you don't specify ``gunicorn.bind``, then a value is constructed
from the relevant options for the OpenERP script (currently
``options.xmlrpc_port`` and ``options.xmlrpc_interface``).

Other simple supported options and their default values are (See also
the `Gunicorn configuration documentation
<http://docs.gunicorn.org/en/latest/configure.html>`) ::

  gunicorn.workers = 4
  gunicorn.timeout = 240
  gunicorn.max_requests = 2000

The recipe sets the proper WSGI entry point according to OpenERP
version, you may manually override that with an option::

  gunicorn.entry_point = mypackage:wsgi.app

You may specify the Gunicorn script name with the
``gunicorn_script_name`` option. The configuration file will be named
accordingly.

The ``gunicorn.preload_databases`` option (one database per line) lets
you specify databases to load in a `post_fork
<http://docs.gunicorn.org/en/latest/configure.html#post-fork>` hook.
With this setting, the worker processes will be ready for requests on these
databases right after their startup. Moreover, Gunicorn does not handle any
request to a worker until it is ready. Therefore, in workloads where
one or a few databases are actually used, this setting keeps the user
experience snappy even in the event of frequent worker restarts, and
allows for graceful restarts (use this for minor changes only).

.. _openerp_command_name:

openerp_command_name
--------------------
.. warning:: as of version 1.7.0, this option is deprecated because of
             its redundancy with :ref:`openerp_scripts`.

OpenERP Command Line Tools (openerp-command for short) is an
alternative set of command-line tools that may someday subsede the
current monolithic startup script. Currently experimental, but
already very useful in development mode.

It is currently enabled if the :ref:`with_devtools` option is on.

This works by requiring the ``openerp-command`` python
distribution, which is not on PyPI as of this writting, but comes
bundled with the current OpenERP trunk (believed to be the future
OpenERP 8).

As for other scripts, you can control its name of the produced script, e.g::

  openerp_command_name = oe

the name defaults otherwise to ``<part_name>_command``. Note that
``oe`` is the classical name for this script outside of the realm of
this buildout recipe.

.. note:: ``openerp-command`` has first been introduced as a separate
          project while OpenERP 7.0 was in development stage. People
          wanting to use it with OpenERP 7.0 can still grab it from
          Launchpad with the ``gp.vcsdevelop`` extension::

            [buildout]
            extensions = gp.vcsdevelop
            vcs-extend-develop = bzr+http://bazaar.launchpad.net/openerp/openerp-command@419#egg=openerp-command

          The latest Launchpad revision is actually the final removal,
          done at the time where it's been included in
          ``lp:openobject-server``.


.. warning::

  On OpenERP 7, do not use to launch production servers, especially in
  an automatic way, ``openerp-command`` is really unstable and that
  may damage your installation.

.. _freeze-to:

freeze-to
---------

This option is meant to produce an extension buildout configuration
that effectively freezes the variable versions and revisions of the
current configuration.

.. note:: supported VCSes for this feature are currently Mercurial,
          Bazaar and Git (excluding Subversion).

It is meant for release processes, and as such includes some
consistency checks to avoid as much as possible issuing a frozen
configuration that could be different from what the developper or
release manager is assumed to have just tested. Namely:

* it works only in offline mode (command-line ``-o`` flag). This is to
  avoid fetching new revisions from VCSes or PyPI
* it fails if some VCS-controlled addons or main software have local
  modifications, including pending merges.

The recommended way to use it is through the command line (all
buildout options can be set this way). Here's an example, assuming the
part is called ``openerp-server-1``::

    bin/buildout -o openerp-server-1:freeze-to=frozen.cfg

This produces a buildout configuration file named ``frozen.cfg``,
with notably an ``openerp-server-1`` part having a :ref:`revisions` option that
freezes everything.

For configurations with several openerp related parts, you can freeze
them together or in different files. This gives you flexibility in the
distributions you may want to produce from a single configuration file::

   bin/buildout -o openerp-server-1:freeze-to=server.cfg openerp-server-2:freeze-to=server.cfg gtkclient:freeze-to=client.cfg

In that latter example, ``server.cfg`` will have the two server parts,
while ``client.cfg`` will have the ``gtkclient`` part only.

.. note:: in DVCSes cases, nothing is done to check that the locally
          extracted revisions are actually pushed where they should.

          Also, if the buildout configuration is itself under version
          control (a good practice), it is not in the recipe scope to
          commit or tag it.
          You are encouraged to use an external release script for
          that kind of purpose.

.. warning:: the recipe will also freeze python distributions installed
             with the ``gp.vcsdevelop`` extension but cannot currently
             protect against local modifications of these.

.. warning:: currently ``freeze-to`` cannot fix eggs versions related
             to non-openerp parts.

.. _freeze-allow-picked-versions:

freeze-allow-picked-versions
----------------------------

This option is to be used in conjunction with :ref:`freeze-to`. If set to
``False``, it will add ``allow-picked-versions = false``
for ``zc.buildout`` versions that support this flag.

.. warning:: in the current state of things, this can cause problems
             if you have non-openerp parts (see the various warnings
             in :ref:`freeze-to`)

.. _extract-downloads-to:

extract-downloads-to
--------------------

Following the same kind of logic as :ref:`freeze-to`, this option allows
to turn a buildout that aggregates from various remote sources
(tarball downloads, VCSes) into a self-contained buildout archive
directory that can be packed for easy distribution.

.. note:: supported VCSes for this feature are currently Mercurial,
          Bazaar and Git (excluding Subversion).

Actually it extracts only the downloaded elements into a target
directory and issues a buildout configuration with local references
only. If that target directory has been itself initialized first with
the *fixed elements* (buildout configuration files, bootstrap scripts,
local addons), then it has all the needed elements, except eggs to
be downloaded from PyPI or the specified index site.

Here is an example, assuming the *fixed elements* are themselves versioned
with Mercurial::

  hg archive ../test-extract && bin/buildout -o openerp:extract-downloads-to=../test-extract

The produced buildout configuration in the target directory is
``release.cfg``. So, for instance, from our ``test-extract`` archive,
the buildout can be executed like this::

  python bootstrap.py && bin/buildout -c release.cfg

or further extended for system-dependent options such as port, db
connection, etc.

The ``extract-downloads-to`` option can be used for several parts
with the same target directory (same as :ref:`freeze-to`).

Furthermore, a default ``freeze-to`` is issued, producing a buildout
configuration called ``extracted_from.cfg`` in the target directory,
for later reference (local modification tracking) or a more
developper-friendly reproduction configuration (ready-made setup to
derive bugfix branches from).

This implication of ``freeze-to`` also has the side effect to enforce the
same rules with respect to uncommitted changes.

Python distributions managed with ``gp.vcsdevelop`` are taken into account.

.. _openerp_options:

OpenERP options
---------------

You can define OpenERP options directly from the buildout file (usually
``buildout.cfg``) in the recipe section.
The OpenERP configuration files are generated by OpenERP itself in the directory
specified by ``etc-directory`` which defaults to the `etc` directory under your
buildout directory.

The settings of the OpenERP configuration files are managed by the
recipe using a dotted notation prefixed by the name of the
corresponding section of the OpenERP config file.
The specified options will just overwrite the existing
options in the corresponding config files. You don't have to replicate all the
options in your section of the buildout file.  If a setting or a section does
not natively exist in the openerp config file, it can be created from there for
your application.

For example you can specify the xmlrpc port for the server or
even an additional option that does not exist in the default config file::

  options.xmlrpc_port = 8069
  options.additional_option = "foobar"

It will end-up in the server config as::

  [options]
  xmlrpc_port = 8069
  additional_option = "foobar"

For the web client you can specify the company url with::

  global.server.socket_port = 8080
  openerp-web.company.url = 'http://anybox.fr'

It will modify the corresponding web client config::

  [global]
  server.socket_port = 8080

  [openerp-web]
  company.url = 'http://anybox.fr'

.. note:: Buildout configuration inheritance (``extends``) is
          especially useful to manage the separation between a
          reusable buildout configuration and local settings.

.. note:: Note that for security reason, the superadmin password is not set by
    default. If you want databases to be manageable through the UI,
    you may either explicitely set that password in the buildout part
    configuration or even set it temporarily in the
    ``etc/openerp.conf`` file. 


Contribute
~~~~~~~~~~

Authors:

 * Christophe Combelles
 * Georges Racinet

Contributors:

 * Jean-Sébastien Suzanne
 * Yannick Vaucher
 * Jacques-Etienne Baudoux
 * Laurent Mignon
 * Leonardo Pistone

The primary branch is on the launchpad:

 * Code repository and bug tracker: https://launchpad.net/anybox.recipe.openerp
 * PyPI page: http://pypi.python.org/pypi/anybox.recipe.openerp

Please don't hesitate to give feedback and especially report bugs or
ask for new features through launchpad at this URL: https://bugs.launchpad.net/anybox.recipe.openerp/+bugs

