anybox.recipe.openerp
=====================

This is a `Buildout <https://github.com/buildout/buildout>`_ recipe that can
download, install and configure one or several OpenERP servers, web clients,
gtk clients and addons modules, from official or custom sources, or any bzr,
hg, git or svn repositories.  It currently supports versions 6.0, 6.1 and 7.0,
with gunicorn deployment and an additional cron worker. It works under Linux
and MacOs. It might work under Windows but it is untested.

For a **quickstart** you can jump to the howto_ section.

A "Buildout recipe" is the engine behind a Buildout "part". A "buildout part"
is a part of a larger application built with the Buildout sandbox build system.
Using Buildout is harmless for your system because it is entirely
self-contained in a single directory: just delete the directory and the
buildout is gone. You never have to use administrative rights, except for
build dependencies.

.. contents::

Recipes
~~~~~~~

You get 3 recipes at once. The recipe to use is the following:

For the server::

    recipe = anybox.recipe.openerp:server

For the web client::

    recipe = anybox.recipe.openerp:webclient

For the gtk client::

    recipe = anybox.recipe.openerp:gtkclient

Default options from zc.recipe.egg
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

This recipe reuses the *zc.recipe.egg:scripts* recipe, so the options
are the same (*eggs*, *interpreter*, etc.), and some changes, documented below.

Consult the documentation here http://pypi.python.org/pypi/zc.recipe.egg

The main useful ones are below:

eggs
----

Starting from version 0.16 of the recipe, you don't need to put anything in
this option by default. But you may specify additional eggs needed by addons,
or just useful ones::

    eggs = 
        ipython
        openobject-library

scripts
-------
.. note:: for scripts needing to call OpenERP internal API or to load
          an OpenERP database prior to execution, check
          ``openerp_scripts`` below.

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
With the ``gtklcient`` and ``webclient`` recipes,
this is the default `interpreter` option of `zc.recipe.egg` that
specifies the name of the Python interpreter that shoud be included in
the``bin`` directory of the buildout::

    interpreter = erp_python

With the ``server`` recipe, the ``interpreter`` option will be ignored,
because it always creates an interpreter with preloaded objects to
bootstrap openerp. Check the ``interpreter_name`` option below for
more details.


Specific options
~~~~~~~~~~~~~~~~

The recipe also adds a few specific options:

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
as the `addons` option (see below)::

  version = bzr lp:openobject-server/6.1 openerp61 last:1

A **nightly** build::

  version = nightly 6.1 20120814-233345

or (dangerously unpinned version)::

  version = nightly 6.1 latest

or even more dangerous::

  version = nightly trunk latest


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

* *TYPE* can be ``bzr``, ``hg``, ``git`` or ``svn``
* *URL* is any URL scheme supported by the versionning tool
* *DESTINATION* is the local directory that will be created (relative or absolute)
* *REVISION* is any version specification supported (revision, tag, etc.)
* *OPTIONS* take the form ``name=value``. Currently the ``subdir``
  option is recognized. If used, the given subdirectory of the
  repository is registered as an addons directory.

Repositories are updated on each build according to the specified
revision. You must be careful with the revision specification.

Buildout offline mode is supported. In that case, update to the
specified revision is performed, if the VCS allows it (Subversion does
not).

.. note:: An additional option is supported for bzr. **'bzr-init'**
          defines the way the bzr branch
          is initialized for addons or server declared with a bzr
          repository path.

          Possible values:

          branch (default)
            Working copy initialized with the command
            ``bzr branch url ...``
          stacked-branch
           Working copy initialized with the command
           ``bzr branch --stacked url ...``

          lightweight-checkout
            Working copy initialized with the command
            ``bzr checkout --lightweight url ...``

revisions
---------

This option allows to further precise what has been specified through
the  ``addons`` and ``version`` options by fixing VCS revisions.

The main use-case it to apply it in an extension buildout
configuration file::

   [buildout]
   extends = base.cfg

   [openerp]
   revisions = 4320  ; main software
               addons-openerp 7109

As you can see in that example, the first token is the target
filesystem path, as in the ``addons`` option, the second one is the
revision, except in the case of the main software (if VCS based), for
which there's no filesystem path.

Some interesting use-cases:

* temporary fixing some revision in cas of upstream regression with no
  impact on your main development configuration (no risk to commit an
  unwanted freeze if the main configuration is itself versionned).
* freezing satisfactory revisions in a release process (the recipe can
  do that automatically for you, see ``freeze-to`` option below).

clean
-----

If set to true, this option will clean remove python object files from
the main server part and addons before any update or install.

Note that tarball downloads get re-extracted afresh in any case.

openerp_scripts
---------------

Introduction and use-cases
``````````````````````````
This option lets you install console scripts provided by any of the loaded eggs,
so that they can access to OpenERP internals and load databases.
Some interesting use-cases:

* specific batch jobs
* introspection tools
* general-purposes test launchers that don't have any knowledge of
  OpenERP specifics
* actually, the main startup scripts themselves (with a default
  configuration, of course)

Usage
`````
This multiline option is similar to the classical ``scripts`` options
of ``zc.recipe.eggs:scripts``. It lets you ask for installation of
console scripts provided by the various Python distribution involved
in the buildout part (including OpenERP itself).

The built console scripts can import all the involved Python
distributions, and have access to a ``session`` object, to issue
OpenERP native calls (see
``interpreter_name`` option below for details on how to use it).

One has to register exactly one console script per line.

As it is the case with ``scripts``, one actually specifies the name of the
entry point to use (we are all used to that entry point being the name
of the resulting script, because that's what ``setup.py install`` does).

Suppose there is a distribution ``my.package`` with the following lines in
its ``setup.py``::

      entry_points="""

      [console_scripts]
      my = my.package.main:run
      """

Now the following configuration extract builds a script called
``my_openerp1``, that can access ``session``::

  [openerp1]
  (...)
  openerp_scripts = my

To control the script name, just do, e.g,::

  [openerp1]
  (...)
  openerp_scripts = my=my_script

This will build it as ``bin/my_script``.

Command-line options and test launchers
```````````````````````````````````````

If ``my.package`` is meant to do OpenERP heavy-lifting, then surely it
will provide a powerful command-line parsing. e.g., to let the end user chose
the database on which to work, etc.

Sometimes, however, the script itself has no knowledge of OpenERP at
all, but still must run after a database has been fully initialized.
The main use case for this is test launchers, such as
`nose <https://nose.readthedocs.org/en/latest/>`_ or simply ``unit2``.
For these, the recipe has a facility to rewrap the script and add some further
command-line options.

In this example, we build ``unit2``, the launcher that comes with
``unittest2``, and wrap it to add the database option::

  [openerp]
  (...)
  openerp_scripts = unit2 command-line-options=-d

You may then run it this way::

   bin/unit2_openerp -d unit-tests-db -- discover some/addon

Notice how ``--`` is used to separate the ``-d`` or
any recipe-related options from the options expected by the script itself.

If one wishes to run the tests with ``nose``, one has further to
require it. In the following example, we also ask for the ``coverage``
package::

  [openerp]
  (...)
  eggs = nose
         coverage
  openerp_scripts = nosetests command-line-options=-d

Here's our test run with coverage and pdb post-mortem::

  bin/nosetests-openerp -d unit-tests-db -- --nologcapture \
           --with-coverage --pdb \
           some/addon/tests/test_one.py

Main startup scripts
````````````````````
The recipe will in all cases build OpenERP startup scripts, according to other
configuration options (gunicorn, tests etc.). These are
actually special cases of the scripts controlled via ``openerp_scripts``.

This allows you (for now) to control the names. For instance, to
replace ``bin/start_openerp`` with ``bin/oerp``, just do::

  [openerp]
  (...)
  openerp_scripts = openerp_starter=oerp

Here's the list of currently available internal entry points. For
these, the ``command-line-options`` modifier has no effect.

:openerp_starter: main OpenERP startup script (dynamically added
                  behing the scenes by the recipe)
:openerp_tester: uniform script to start OpenERP, launch all tests and
                 exit. This can be achieved with the main startup
                 scripts, but options differ among OpenERP versions.
                 (also dynamically added behind the scenes).
:openerp_cron_worker: entry point for the cron worker script that gets
                      built for gunicorn setups.
:oe: entry point declared by ``openerp-command`` and used by the recipe.
:gunicorn: entry point declared ``gunicorn`` and used by the recipe.

script_name
-----------

.. warning:: as of version 1.7.0, this option is deprecated because of its
             redundancy with ``openerp_scripts``.

OpenERP startup scripts are created in the `bin` directory. By default the name is:
start_<part_name>, so you can have several startup scripts for each part if you
configure several OpenERP servers or clients. You can pass additional typical
arguments to the server via the startup script, such as -i or -u options.

You can choose another name for the script by using the *script_name*
option ::

    script_name = start_erp  

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

The bootstrapping facility may also be used within a script installed
by an egg; just insert this in your code to get the session object as
if you were in the interpreter::

    from anybox.recipe.openerp.startup import Session
    session = Session()

.. note:: this facility is new in version 1.6.0, and tested with
          OpenERP 7 only for now.

startup_delay
-------------

Specifies a delay in seconds to wait before actually launching OpenERP. This
option was a preliminary hack to support both gunicorn instance and a legacy
instance.  The Gunicorn startup script (see below) itself is not affected by
this setting ::

    startup_delay = 3

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

test_script_name
----------------
.. warning:: as of version 1.7.0, this option is deprecated because of its
             redundancy with ``openerp_scripts``.

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

base_url
--------

URL from which to download official and nightly versions
(assuming the archive filenames are constistent with those in
OpenERP download server). This is a basic mirroring capability::

    base_url = http://download.example.com/openerp/

openerp-downloads-directory
---------------------------

Allows to share OpenERP downloads among several buildouts. You should put this
option in your ``~/.buildout/default.cfg`` file.  It specifies the destination
download directory for OpenERP archives. The path may be absolute or relative
to the buildout directory.

Example::

    [buildout]
    openerp-downloads-directory = /home/user/.buildout/openerp-downloads

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

Other supported options and their default values are::

  gunicorn.workers = 4
  gunicorn.timeout = 240
  gunicorn.max_requests = 2000

The recipe sets the proper WSGI entry point according to OpenERP
version, you may manually override that with an option::

  gunicorn.entry_point = mypackage:wsgi.app

Finally, you can specify the Gunicorn script name with the
``gunicorn_script_name`` option. The configuration file will be named
accordingly.

openerp_command_name
--------------------
.. warning:: as of version 1.7.0, this option is deprecated, check
   ``openerp_scripts`` for more details.

OpenERP Command Line Tools (openerp-command for short) is an
alternative set of command-line tools that may someday subsede the
current monolithic startup script. Currently experimental, but
already very useful in development mode.

It is currently enabled if the ``with_devtools`` option is on.

This works by requiring the ``openerp-command`` python
distribution, which is not on PyPI as of this writting. You may want
to use the ``vcsdevelop`` extension to get it from Launchpad::

  [buildout]
  extensions = gp.vcsdevelop
  vcs-extend-develop = bzr+http://bazaar.launchpad.net/openerp/openerp-command#egg=openerp-command

As for other scripts, you can control its name of the produced script, e.g::

  openerp_command_name = oe

the name defaults otherwise to ``<part_name>_command``. Note that
``oe`` is the classical name for this script outside of the realm of
this buildout recipe.

.. warning::

  Do not use to launch production servers, especially in an automatic
  way, openerp-command is really unstable and that may damage your
  installation.

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
with notably an ``openerp-server-1`` part having a ``revisions`` option that
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

freeze-allow-picked-versions
----------------------------

This option is to be used in conjunction with ``freeze-to``. If set to
``False``, it will add ``allow-picked-versions = false``
for ``zc.buildout`` versions that support this flag.

.. warning:: in the current state of things, this can cause problems
             if you have non-openerp parts (see warning in ``freeze-to``
             documentation).


extract-downloads-to
--------------------

Following the same kind of logic as ``freeze-to``, this option allows
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

The ``extract-downloads-to`` options can be used for several parts
with the same target directory (same as ``freeze-to``).

Furthermore, a default ``freeze-to`` is issued, producing a buildout
configuration called ``extracted_from.cfg`` in the target directory,
for later reference (local modification tracking) or a more
developper-friendly reproduction configuration (ready-made setup to
derive bugfix branches from).

This implication of ``freeze-to`` also has the side effect to enforce the
same rules with respect to uncommitted changes.

Python distributions managed with ``gp.vcsdevelop`` are taken into account.


OpenERP options
---------------

You can define OpenERP options directly from the buildout file (usually
``buildout.cfg``) in the recipe section.
The OpenERP configuration files are generated by OpenERP itself in the directory
specified by ``etc-directory`` which defaults to the `etc` directory under your
buildout directory.
The settings of the OpenERP configuration files can be controlled using a
dotted notation prefixed by the name of the corresponding section of the
OpenERP config file. The specified options will just overwrite the existing
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


.. note:: Note that for security reason, the superadmin password is not set by
    default. If you want to create a database you should temporary set it manually
    in the etc/openerp.conf file



.. _howto:

How to create and bootstrap a buildout
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

To create a buildout and run the build, you just need **1 file** and **2 commands**:

- Create a single ``buildout.cfg`` file.
- Be sure you installed all your build dependencies
- Bootstrap the buildout with: ``python bootstrap.py``
- Run the build with: ``bin/buildout``

The same with more details below :

Creating the buildout
---------------------

Create a ``buildout.cfg`` file in an empty directory, containing the
configuration of the `example 6.1`_ section.

.. _dependencies:

Installing build dependencies
-----------------------------

You basically need typical development tools needed to build all the Python
dependency eggs of OpenERP. You can do this by yourself with your system or
Linux distribution.

Or if you're using a Debian system, we provide a single dependency package you
can use to install all dependencies in one shot:

Add the following line in your ``/etc/apt/sources.list``::

  deb http://apt.anybox.fr/openerp common main

Install the dependency package::

  $ sudo aptitude update 
  $ sudo aptitude install openerp-server-system-build-deps

You can uninstall this package with `aptitude` after the build to
automatically remove all un-needed dependencies, but you need to
install *run dependencies* before that ::

  $ sudo aptitude install openerp-server-system-run-deps
  $ sudo aptitude remove openerp-server-system-build-deps

Please note that these package will have your system install the
*client* part of PostgreSQL software only. If you want a
PostgreSQL server on the same host, that's not in the recipe scope,
just install it as well.

Bootstrapping the buildout
--------------------------

Bootstrapping the buildout consists in creating the basic structure of the buildout, and installing buildout itself in the directory.

The easiest and recommended way to bootstrap is to use a ``bootstrap.py`` script::

  $ wget https://raw.github.com/buildout/buildout/master/bootstrap/bootstrap.py
  $ python bootstrap.py

As an alternative and more complicated solution, you may also bootstrap by
creating a virtualenv, installing zc.buildout, then run the bootstrap::

  $ virtualenv sandbox
  $ sandbox/bin/pip install zc.buildout
  $ sandbox/bin/buildout bootstrap

Running the build
-----------------

Just run ::

  $ bin/buildout

Starting OpenERP
----------------

Just run ::

  $ bin/start_openerp


.. _example 6.1:

Example OpenERP 6.1 buildout
~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Here is a very simple example for a latest OpenERP 6.1 nightly and a
custom addon hosted on Bitbucket:

::

    [buildout]
    parts = openerp 
    versions = versions
    find-links = http://download.gna.org/pychart/
    
    [openerp]
    recipe = anybox.recipe.openerp:server
    # replace '6.1' with 'trunk' to get a 7.0 current nightly:
    version = nightly 6.1 latest
    addons = hg https://bitbucket.org/anybox/anytracker addons-at default

    [versions]
    MarkupSafe = 0.15
    Pillow = 1.7.7
    PyXML = 0.8.4
    babel = 0.9.6
    feedparser = 5.1.1
    gdata = 2.0.16
    lxml = 2.3.3
    mako = 0.6.2
    psycopg2 = 2.4.4
    pychart = 1.39
    pydot = 1.0.28
    pyparsing = 1.5.6
    python-dateutil = 1.5
    python-ldap = 2.4.9
    python-openid = 2.2.5
    pytz = 2012b
    pywebdav = 0.9.4.1
    pyyaml = 3.10
    reportlab = 2.5
    simplejson = 2.4.0
    vatnumber = 1.0
    vobject = 0.8.1c
    werkzeug = 0.8.3
    xlwt = 0.7.3
    zc.buildout = 1.5.2
    zc.recipe.egg = 1.3.2
    zsi = 2.0-rc3


.. note:: with OpenERP 6.1 the web client is natively included in the server as a
    simple module. In that case you don't need to write a separate part for the web
    client, unless that's what you really want to do.


Example OpenERP 6.0 buildout
~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Here is a sample buildout with version specification, 2 OpenERP servers (with
one using the latest 6.0 branch on the launchpad) using only NETRPC and
listening on 2 different ports, and 2 web clients::

    [buildout]
    parts = openerp1 web1 openerp2 web2
    #allow-picked-versions = false
    versions = versions
    find-links = http://download.gna.org/pychart/
    
    [openerp1]
    recipe = anybox.recipe.openerp:server
    version = 6.0.3
    options.xmlrpc = False
    options.xmlrpcs = False
    
    [web1]
    recipe = anybox.recipe.openerp:webclient
    version = 6.0.3
    
    [openerp2]
    recipe = anybox.recipe.openerp:server
    version = bzr lp:openobject-server/6.0 openobject-server-6.x last:1

    options.xmlrpc = False
    options.xmlrpcs = False
    options.netrpc_port = 8170
    
    [web2]
    recipe = anybox.recipe.openerp:webclient
    version = 6.0.3
    global.openerp.server.port = '8170'
    global.server.socket_port = 8180
    
    [versions]
    MarkupSafe = 0.15
    Pillow = 1.7.7
    anybox.recipe.openerp = 0.9
    caldav = 0.1.10
    collective.recipe.cmd = 0.5
    coverage = 3.5
    distribute = 0.6.25
    feedparser = 5.0.1
    lxml = 2.1.5
    mako = 0.4.2
    nose = 1.1.2
    psycopg2 = 2.4.2
    pychart = 1.39
    pydot = 1.0.25
    pyparsing = 1.5.6
    python-dateutil = 1.5
    pytz = 2012b
    pywebdav = 0.9.4.1
    pyyaml = 3.10
    reportlab = 2.5
    vobject = 0.8.1c
    z3c.recipe.scripts = 1.0.1
    zc.buildout = 1.5.2
    zc.recipe.egg = 1.3.2
    Babel = 0.9.6
    FormEncode = 1.2.4
    simplejson = 2.1.6


Other sample buildouts
~~~~~~~~~~~~~~~~~~~~~~

Here are a few ready-to-use buildouts:

(Be sure to install system dependencies_ first)

OpenERP with the development branches of the Magento connector addons::

  $ hg clone https://bitbucket.org/anybox/openerp_connect_magento_buildout
  $ cd openerp_connect_magento_buildout
  $ python bootstrap.py
  $ bin/buildout
  $ bin/start_openerp

OpenERP with the development branches of the Prestashop connector addons::

  $ hg clone https://bitbucket.org/anybox/openerp_connect_prestashop_buildout
  $ cd openerp_connect_prestashop_buildout
  $ python bootstrap.py
  $ bin/buildout
  $ bin/start_openerp

Other examples are available in the ``buildbot`` subdirectory of the
source distribution archive of this recipe (the ``tar.gz`` file that
can be downloaded `from the PyPI
<http://pypi.python.org/pypi/anybox.recipe.openerp>`_), and are
continuously tested in the
`anybox buildbot <http://buildbot.anybox.fr/>`_ which is powered by
`anybox.buildbot.openerp <http://pypi.python.org/pypi/anybox.buildbot.openerp>`_.


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

