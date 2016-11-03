Configuration reference
=======================

This is a `Buildout <https://github.com/buildout/buildout>`_ recipe that can
download, install and configure one or several Odoo servers, web clients,
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
The intents of this section is to highlights a few facts that we've
found especially useful. People should refer to the
`reference zc.buildout documentation
<https://pypi.python.org/pypi/zc.buildout/2.2.1>`_
and in particular to the `configuration file syntax
<https://pypi.python.org/pypi/zc.buildout/2.2.1#configuration-file-syntax>`_
(these links may have to be adapted for the version in use).

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

An extra dependency of the recipe gets required at runtime like this::

  recipe = anybox.recipe.openerp[bzr]:server

.. note:: inline comments

          As of version 1.9 of the recipe, inline comments starting
          with a semicolon *not at the beginning of a line* are
          supported in the recipe's specific options, and especially
          in the multi line ones, whereas ``zc.buildout`` does not
          support them.

          For more detail, check
          :py:func:`anybox.recipe.openerp.utils.option_splitlines`.

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


Odoo recipes
~~~~~~~~~~~~

There are three different recipes bundled with
``anybox.recipe.openerp``. The option line to put in your part (see
:ref:`buildout_conf_parts`) is the following.

Server
------
::

    recipe = anybox.recipe.openerp:server

.. note:: If you plan on using Launchpad's short Bazaar branch notation
          (``lp:``), then you need to add the ``bzr`` extra-dependency::

            recipe = anybox.recipe.openerp[bzr]:server

Web client
----------
::

    recipe = anybox.recipe.openerp:webclient

GTK client
----------
::

    recipe = anybox.recipe.openerp:gtkclient

.. note:: from OpenERP 7.0 onwards, the web and gtk clients aren't
          that useful anymore.

Options for assembly and source management
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

.. _version:

version
-------

Specifies the Odoo version to use. It can be:

* The **version number** of an official Odoo (server, web client or gtk client)::

    version = 6.0.3

* A **custom download**::

    version = url http://example.com/openerp.tar.gz

* An absolute or a relative **path**::

    version = path /my/path/to/a/custom/openerp

* A custom **bzr, hg, git or svn** branch or repository. The syntax is the same
  as with the :ref:`addons` option::

    recipe = anybox.recipe.openerp[bzr]:server
    version = bzr lp:openobject-server/6.1 openerp61 last:1

  .. note:: the ``[bzr]`` extra dependency declaration is useful for
            resolution of the ``lp:`` address shortcuts.

* A **nightly** build::

    version = nightly 6.1 20120814-233345

* or (dangerously unpinned version)::

    version = nightly 6.1 latest

*  or even more dangerous::

     version = nightly trunk latest

.. _addons:

addons
------

Specifies additional Odoo addons, either a local path or a remote
repository.

Example::

  recipe = anybox.recipe.openerp[bzr]:server
  addons = local ../some/relative/path/for/custom_addons/
           local /some/other/absolute/path/for/custom_addons
           bzr lp:openobject-addons/trunk/    addons0 last:1
           hg  http://example.com/some_addons addons1 default
           git http://example.com/some_addons addons2 master
           svn http://example.com/some_addons addons3 head
           bzr lp:openerp-web/trunk/ openerp-web last:1 subdir=addons

Remote repositories can either contain addons subdirectories, or
be a single addon. In that latter case, called a *standalone
addon*, the :ref:`group option <option_group>` must be used to place
the addon in an intermediate subdirectory, to match the structure expected by
Odoo.

Standalone addons are not supported in the local case (the
directory is considered under full responsibility of the user).


.. note:: the ``[bzr]`` extra-dependency declaration as showcased
          above in the ``recipe`` line is necessary for
          resolution of ``lp:`` launchpad address shortcuts.

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

.. _option_group:

The ``group`` addons option
```````````````````````````
.. note:: new in version 1.9.0

The purpose of this option is to accomodate *standalone
addons*. Indeed, Odoo expects its configuration to refer to
directory that contain addons, but some people might prefer to version
their addons in separate VCS repositories.

The ``group`` option allows to specify an intermediate directory into
which the standalone addon should actually be set::

   git http://example.com/some_addons some/target_dir group=some_group

The addon will end up in ``some/some_group/target_dir`` and
``some/some_group`` will be the directory registered to Odoo

Even if you have only standalone addon to register, you must do it
with the ``group`` option.

.. warning:: up to 1.8 versions, the recipe used to
             create an intermediate directory silently for standalone
             addons, this is not supported any more


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

.. note:: new in version 1.7.0

Possible values:

:branch (default):  Working copy initialized with the command
                    ``bzr branch url ...``

:stacked-branch:  Working copy initialized with the command
                  ``bzr branch --stacked url ...``
:lightweight-checkout: Working copy initialized with the command
                       ``bzr checkout --lightweight url ...``

.. _git_depth:

The ``depth`` Git option
````````````````````````
.. note:: new in vertion 1.9.0


**depth** is a per-repository configurable option to create and
maintain Git shallow clones. It allows to specify the maximum history
one wishes to keep in the local repository, hence minimizing the disk
space needed and initial cloning time.

Example::

  version = git http://github.com/odoo/odoo.git odoo 8.0 depth=1

You may also use this option to override the global ``git-depth``
option, and in particular cancel it by specifying ``None``::

  version = git http://github.com/odoo/odoo.git odoo 8.0 depth=None

Currently, adding this option to an existing repository does not
reduce the disk footprint immediately.

.. warning:: the ``depth`` option is abrasive, and should be avoided
             on developper setups: you may lose unpushed commits.
             It is, however, a good fit for automated build or
             deployment systems on which the history does not usually
             matter.

.. _git_sha_branch:

Git SHA pinning and the ``branch`` option
`````````````````````````````````````````

The ``branch`` option is used to specify a branch *indication* to help
retrieving remote commits that can't be fetched directly.

In Git, a commit can never be fetched by its SHA, but the recipe
supports is nevertheless, so that version pinning can be achieved
without enough authority to add tags in remote.

To do so, the recipe must perform first a broader fetch, then hope the
wished commit has become available locally. The ``branch`` option
narrows said fetch for better efficiency and reliability.

Because of the potential problems mentioned above, the recipe emits a
warning when coming across a SHA pin. You can disable this warning by
setting ``git-warn-sha-pins = False``.

.. note:: the ``branch`` option is new in vertion 1.9.1

.. warning:: non tagged commits can become unreachable, especially
             if the remote repository gets lots of rebasing. If
             possible, pinning on tags is always to be preferred.

.. _merges:

merges
------
Specify which VCS branches need to be merged into repositories
specified under :ref:`addons` or :ref:`version`. The syntax is
the same as for repositories specified under these directives.

Currently only merges on bzr and git repositories are supported
(requires git 1.8)

.. note:: new in version 1.9.0

.. _eggs:

eggs
----
This option behaves like the identically named one of the most common
`zc.recipe.egg <https://pypi.python.org/pypi/zc.recipe.egg>`_.

Starting from version 0.16 of the recipe, you don't need to put anything in
this option by default: the recipe is supposed to add all needed
dependencies for Odoo by itself, but you have to specify additional
eggs needed by addons, or just useful ones::

    eggs = ipython
           python-ldap
           openobject-library

.. _apply_requirements_file:

apply-requirements-file
-----------------------
.. note:: new in version 1.9.2

Default value: ``False``

If set to ``True``, this boolean option makes the recipe read Odoo's
``requirements.txt`` file if available, and apply its prescriptions.

Precedence among requirements
`````````````````````````````
In short, Odoo's requirement file has the lowest precedence of all
systems that can manage versions of Python libraries within the recipe context:

* ``zc.buildout`` comes with its own native way of expressing wished
  Python versions, with a dedicated configuration section, which is by default
  ``[versions]``. This native system has precedence over the contents of
  Odoo's requirement file.
* all kinds of ``develop`` directives have precedence over Odoo's
  requirement file. This includes the ``vcs-extend-develop`` of the
  ``gp.vcsdevelop`` extension.

Requirements file limitations
`````````````````````````````

In case the requirements file you use is not properly supported, we
suggest as a workaround to you convert it temporarily to
``[versions]`` statements, and get in touch with the recipe's
developers.

.. note:: At the time of this writing, the ``requirements.txt`` file shipping
          within Odoo's main 8.0 branch is fully supported, but :

          * you are free to use any alternative branch, including your
            own baked
          * the mainline requirements file may change in the future.

Only a small subset of the `pip's requirement specifiers
<https://pip.pypa.io/en/latest/reference/pip_install.html#requirement-specifiers>`_
is actually supported, notably:

* version inequalities, such as ``>=2.0`` and boolean expressions are
  not currently implemented. They will be if needed, and you should
  get an understandable message about the condition being "too complicated"
* no specifier involving network operations is supported. In
  particular, the VCS URLs are not (to workaround that, use
  ``gp.vcsdevelop``), and the ``-r`` (``--requirements``) specifiers
  work for local files only (path relative to the Odoo part directory).

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

vcs-revert
----------

Possible value: ``on-merge`` (more are been thought of)

If this option is used with the ``on-merge`` value, the VCS repositories
will be reverted, **losing all local modifications** after the
pull/update, right before the merge.

This is especially useful in unattended executions, to clean up any
previous failed merges.

Currently only bzr and git repositories get reverted.

.. note:: new in version 1.9.0

vcs-clear-retry
---------------

If ``True`` failed updates are cleared and retried once.
This is intended for brittle VCSes from CI robots.

vcs-clear-locks
---------------

Some VCS systems can leave locks after some failures and provide a separate
way to break them. If ``True``,the repo will break any locks prior to
operations (mostly useful for automated agents, such as CI robots)

git-depth
---------

This is the global variant of the :ref:`git_depth` option (please read
the provisions there carefully, as it is potentially dangerous).

Setting a value to ``git-depth`` is the same as doing it for all
involved Git repositories, but does not have precedence over
per-repository settings (which can also remove it altogether).

This option is especially meant for automated tools (continuous
integration, unattended deployment) as
they can easily add it from the command-line to any buildout.

.. note:: new in version 1.9.0

.. _openerp_options:

Odoo options
~~~~~~~~~~~~

With the Odoo buildout recipes, Odoo options are managed
directly from the buildout file (usually
``buildout.cfg``) from the part.

The Odoo configuration files are generated by Odoo itself in the directory
specified by ``etc-directory``, which defaults to the `etc` directory under your
buildout directory.

The settings of the Odoo configuration files are specified using a
dotted notation in which the fist segment is the name of the
corresponding section of the Odoo config file and the second is the
option name.

The specified options will just overwrite the existing
options in the corresponding config files. You don't have to replicate all the
options in your section of the buildout file.  If a setting or a section does
not natively exist in the openerp config file, it can be created from there for
your application.

For example you can specify the xmlrpc port for the server or
even an additional option that does not exist in the default config file::

  options.xmlrpc_port = 8069
  options.additional_option = "foobar"

It will end-up in the server configuration as::

  [options]
  xmlrpc_port = 8069
  additional_option = "foobar"

For the web client you can specify the port and company url with::

  global.server.socket_port = 8080
  openerp-web.company.url = 'http://anybox.fr'

It will modify the corresponding web client config::

  [global]
  server.socket_port = 8080

  [openerp-web]
  company.url = 'http://anybox.fr'

.. note:: Buildout :ref:`configuration inheritance <extends>` is
          especially useful to manage the separation between a
          reusable buildout configuration and local settings.

.. note:: Note that for security reasons, the superadmin password is not set by
    default. If you want databases to be manageable through the UI,
    you may either explicitely set that password in the buildout part
    configuration or even set it temporarily in the
    ``etc/openerp.conf`` file.


Options for executables generation and serving
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

.. _script_name:

script_name
-----------

.. warning:: as of version 1.7.0, this option is deprecated because of its
             redundancy with :ref:`openerp_scripts`.

Odoo startup scripts are created in the `bin` directory. By default
the name is ``start_<part_name>``, so you can have several startup
scripts for each part if you configure several Odoo servers or clients.

You can pass additional typical
arguments to the server via the startup script, such as -i or -u options.

You can choose another name for the script by using the *script_name*
option ::

    script_name = start_erp

gevent_script_name
------------------

..note :: for Odoo version 8 and onwards

Lets you control the name of the asynchronous longpolling listener
leveraging ``gevent`` (known as ``openerp-gevent`` in the basic
install).

The default is ``gevent_<PART>``.

.. note:: new in version 1.8.4


.. _openerp_scripts:

openerp_scripts
---------------
This option lets you install console scripts provided by any of the loaded eggs,
so that they can access to Odoo internals and load databases.

.. note:: new in version 1.7.0

Here we describe the format of the option only.
For explanation about what it means and how to use it, please refer to
:doc:`/scripts`.

The option is multiline. Each line specifies exactly one
script, and must respect the following format:

  ``ENTRY_POINT_NAME[=WISHED_SCRIPT_NAME] [MODIFIER [MODIFIER […]]]``

Each modifier takes the ``MODIFIER_NAME=MODIFIER_VALUE`` form.
No whitespace is allowed in modifiers, entry point, nor produced script names.

Here's the list of currently available modifiers, with links inside :doc:`the
dedicated chapter about Odoo scripts </scripts>`).

:command-line-options: :ref:`command_line_options`
:arguments: :ref:`arguments_session`
:openerp-log-level: :ref:`openerp_log_level`

Full example::

  openerp_scripts = my_script arguments=session
                    my_other_script=actual-script-name arguments=3,session
                    nosetests=nosetests command-line-options=-d
                    sphinx-build=sphinx-build openerp-log-level=ERROR command-line-options=-d


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

.. note:: new in version 1.8.0

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

.. _gunicorn:

gunicorn
--------

Gunicorn integration is only supported on Odoo ≥ 6.1.
Any value of this option makes the recipe generate a script to start
Odoo with Gunicorn and (*new in version 1.1*) a dedicated script to
handle cron jobs.

For OpenERP 6.1, the only accepted values are ``direct`` and
``proxied``. Any value is suitable for OpenERP ≥ 7

Proxied mode
````````````
For OpenERP 6.1, a special value of the ``gunicorn`` option is to be
used if you plan to run Gunicorn behind a reverse proxy::

    gunicorn = proxied

This behaviour has been kept for OpenERP ≥ 7 to keep
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
from the relevant options for the Odoo script (currently
``options.xmlrpc_port`` and ``options.xmlrpc_interface``).

Other simple supported options and their default values are (See also
the `Gunicorn configuration documentation
<http://docs.gunicorn.org/en/latest/configure.html>`_) ::

  gunicorn.workers = 4
  gunicorn.timeout = 240
  gunicorn.max_requests = 2000

The recipe sets the proper WSGI entry point according to Odoo
version, you may manually override that with an option::

  gunicorn.entry_point = mypackage:wsgi.app

You may specify the Gunicorn script name with the
``gunicorn_script_name`` option. The configuration file will be named
accordingly.

The ``gunicorn.preload_databases`` option (one database per line) lets
you specify databases to load in a `post_fork hook
<http://docs.gunicorn.org/en/latest/configure.html#post-fork>`_.
With this setting, the worker processes will be ready for requests on these
databases right after their startup. Moreover, Gunicorn does not handle any
request to a worker until it is ready. Therefore, in workloads where
one or a few databases are actually used, this setting keeps the user
experience snappy even in the event of frequent worker restarts, and
allows for graceful restarts (use this for minor changes only).

.. _server_wide_modules:

server_wide_modules
-------------------
.. note:: new in version 1.9.0

This multi-line option lets you specify addons to be loaded directly
at startup, independently of what is installed in the database.

It plays the same role as the ``--load`` command-line option of the main Odoo
startup script, with lower precedence if the latter is also specified.
Examples::

  server_wide_modules = custom_homepage

Since there is no entry in the Odoo configuration file corresponding
to ``--load``, this recipe option helps bringing uniformity accross
running instances of the project by enclosing this notion in
the shippable configuration.

It can also be leveraged by other scripts or recipe subsystems,
notably the :ref:`gunicorn startup script <gunicorn>`.

.. note:: in any case, the ``web`` addon is loaded as a server-wide one.

.. _openerp_command_name:

openerp_command_name
--------------------
.. warning:: as of version 1.7.0, this option is deprecated because of
             its redundancy with :ref:`openerp_scripts`.

Odoo Command Line Tools (openerp-command for short) is an
alternative set of command-line tools that may someday subsede the
current monolithic startup script. Currently experimental, but
already very useful in development mode.

It is currently enabled if the :ref:`with_devtools` option is on.

This works by requiring the ``openerp-command`` python
distribution, which is not on PyPI as of this writting, but comes
bundled with the current Odoo trunk (believed to be the future
Odoo 8).

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
            vcs-extend-develop = bzr+http://bazaar.launchpad.net/~openerp/openerp-command/7.0#egg=openerp-command


.. warning::

  On OpenERP 7, do not use to launch production servers, especially in
  an automatic way, ``openerp-command`` is really unstable and that
  may damage your installation.



scripts
-------
.. note:: This option is useful for general purpose scripts
          only. For scripts related to Odoo, see
          :doc:`/scripts`, and the :ref:`openerp_scripts` option.

This option controls the generation of console scripts declared by the
various involved Python distributions (either directly required with
the :ref:`eggs` option, or by dependency).

By default, no such script is generated, but you may specify some
according to your needs, with the same semantics as in ``zc.recipe.egg``.

        scripts = change_tz

In the current state, beware to *not* require the same script in different
parts or rename them. See
https://bugs.launchpad.net/anybox.recipe.openerp/+bug/1020967 for
details.


.. _startup_delay:

startup_delay
-------------

Specifies a delay in seconds to wait before actually launching Odoo. This
option was a preliminary hack to support both gunicorn instance and a legacy
instance.  The Gunicorn startup script (see below) itself is not affected by
this setting ::

    startup_delay = 3

Options for development, QA and introspection
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

.. _with_devtools:

with_devtools
-------------
Allows to load development and install useful devlopment and testing
tools, notably the following scripts:

* ``test_openerp``: a uniform test launcher for all supported
  versions. See test_script_name option below for details.
* ``openerp_command``: see openerp_command_name option below for
  details. Not installed for Odoo major versions less than or equal to 6.1.

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
regular startup script is to bring uniformity across Odoo versions
by tweaking options internally.

*As of version 1.8.2*, the ``--install-all`` additional option will be
expanded on-the-fly as ``-i`` on all available modules (don't confuse
with ``-i all``: the latter is equivalent to ``-i base``).


.. _interpreter_name:

interpreter_name
----------------

The recipe will automatically create a python interpreter with a
``session`` object that can bootstrap Odoo with a database right
away. You can use that for interactive sessions or to launch a script::

    $ bin/python_odoo
    To start the Odoo working session, just do:
        session.open(db=DATABASE_NAME)
    or, to use the database from the buildout part config:
        session.open()
    All other options from buildout part config do apply.
    Then you can issue commands such as:
        session.registry('res.users').browse(session.cr, 1, 1)
    Or using new api:
        session.env['res.users'].browse(1)
    >>>

The interpreter name is  ``python_<part_name>`` by default; but it can
be explicitely set like this::

    interpreter_name = my_py

If you want *not* to have the interpreter, juste do

    interpreter_name =

If you want to wrap a python script with such session objects you need to use
the :ref:`openerp_scripts` option. See :doc:`/scripts` and especially
:ref:`arguments_session`.

If you want a more comfortable Python console like
`IPython <http://ipython.org>`_ or
`bPython <http://bpython-interpreter.org>`_, take a
look at :ref:`interactive_consoles`.

.. note:: this facility is new in version 1.6.0, and tested with
          OpenERP ≥ 6.1 only for now.


interpreter
-----------
With the ``gtkclient`` and ``webclient`` recipes,
this behaves like the `interpreter` option of `zc.recipe.egg`: it
gives you a Python interpreter in the ``bin`` subdirectory of the buildout::

    interpreter = erp_python

With the ``server`` recipe, the ``interpreter`` option will be ignored,
because this recipe always creates an interpreter with preloaded objects to
bootstrap openerp, and these depend on the configuration.
Check :ref:`interpreter_name` for more details.




Options for download and caching strategies
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Let us start by listing a few global buildout options (to be put in
the ``[buildout]`` section), whose scope is much larger than the
Odoo recipe.

:eggs-directory: control where eggs are stored after download and/or
                 build and reciprocally acts as a cache.
:index: specifies where to get informations about distributions not found in
        ``eggs-directory``.
:find-links: direct URLs to look for distributions
:allow-hosts: white list of URL patterns allowed for distributions
              download. Great to exclude the numerous useless sites
              that setuptools may want to crawl and which tend to
              break each time a new version gets referenced on PyPI.

The Odoo recipes define a few more.


.. _base_url:

base_url
--------
This option is local to the *part*.

URL from which to download official and nightly versions
(assuming the archive filenames are constistent with those in
Odoo download server). This is a basic mirroring capability::

    base_url = http://download.example.com/openerp/


.. _openerp-downloads-directory:

openerp-downloads-directory
---------------------------
This is an option for the ``[buildout]`` section

Allows to share Odoo downloads among several buildouts. You should put this
option in your ``~/.buildout/default.cfg`` file.  It specifies the destination
download directory for Odoo archives. The path may be absolute or relative
to the buildout directory.

Example::

    [buildout]
    openerp-downloads-directory = /home/user/.buildout/openerp-downloads



Options for release and packaging
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

.. note:: release and packaging should be provided by dedicated
          executables, not by options. These options should disappear
          at some point between 1.8 and 1.9 versions.

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
