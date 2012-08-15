anybox.recipe.openerp
=====================

This is a `Buildout <https://github.com/buildout/buildout>`_ recipe for
downloading, installing and configuring one or several OpenERP servers, web
clients and/or gtk clients. It currently supports versions 6.0 and 6.1, custom
branches, custom addons and gunicorn deployment. For a quickstart you can
jump to the example section.

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

Consult the documentation here http://pypi.python.org/pypi/zc.recipe.egg/1.3.2

The main useful ones are below:

eggs
----

Starting from version 0.16 of the recipe, you don't need to put anything in
this option by default.  But you may specify additional eggs needed by addons,
or just useful ones::

    eggs = 
        ipython
        openobject-library

scripts
--------

The behaviour of this option is slightly modified :
by default, no script other than those directly related to OpenERP are
generated, but you may specify some explicitely, with the same semantics as the
normal behaviour (we simply set an empty default value, which means to not
produce scripts)::

        scripts =
            change_tz

In the current state, beware to *not* require the same script in different
parts or rename them. See
https://bugs.launchpad.net/anybox.recipe.openerp/+bug/1020967 for details.

interpreter
-----------

This is the default `interpreter` option of `zc.recipe.egg` that specifies the name 
of the Python interpreter that shoud be included in the ``bin`` directory of the buildout::

    interpreter = erp_python


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

or (dangerous)::

  version = nightly 6.1 latest


addons
------

Specifies additional addons, either a local path or a repository.

Example::

  addons = local ../some/relative/path/for/custom_addons/
           local /some/other/absolute/path/for/custom_addons
           bzr lp:openobject-addons/trunk/    addons0 last:1
           hg  http://example.com/some_addons addons1 default
           git http://example.com/some_addons addons2 master
           svn http://example.com/some_addons addons3 head
           bzr lp:openerp-web/trunk/ openerp-web last:1 subdir=addons

When using ``local`` paths you can either specify a directory holding
addons, or a single one. In that latter case, it will be actually
placed one directory below
    
For remote repositories the syntax is:

``TYPE  URL  DESTINATION  REVISION  [OPTIONS]``

* *TYPE* can be ``bzr``, ``hg``, ``git`` or ``svn``
* *URL* is any URL scheme supported by the versionning tool
* *DESTINATION* is the local directory that will be created (relative or absolute)
* *REVISION* is any version specification supported (revision, tag, etc.)
* *OPTIONS* take the form ``name=value``. Currently, only the ``subdir``
  option is recognized. If used, the given subdirectory of the
  repository is registered as an addons directory.

Repositories are updated on each build according to the specified
revision. You have to be careful with the revision specification.

Buildout offline mode is supported. In that case, update to the
specified revision is performed, if the VCS allows it (Subversion does not).

script_name
-----------

Startup scripts are created in the `bin` directory. By default the name is:
start_<part_name>, so you can have several startup scripts for each part if you
configure several OpenERP servers or clients. You can pass additional typical
arguments to the server via the startup script, such as -i or -u options.

You can choose another name for the script by using the *script_name*
option ::

    script_name = start_erp  

startup_delay
-------------

Specifies a time in seconds to wait within the startup
script before actually launching OpenERP. The Gunicorn startup script (see
below) is not affected by this setting ::

    startup_delay = 3

with_devtools
-------------

Allows to load development and useful testing tools, such as
``anybox.testing.datetime``. False by default::

    with_devtools = true

base_url
--------

URL to download official and nightly versions from
(assuming the archive filenames are constistent with those in
OpenERP download server). This is a basic mirroring capability::

    base_url = http://download.example.com/openerp/

openerp-downloads-directory
---------------------------

Specifies the destination download directory for OpenERP archives. The path may
be absolute or relative to thebuildout directory.  By setting it in your
``default.cfg``, you may share the downloads among different buildouts.

Example::

    [buildout]
    openerp-downloads-directory = /home/user/.buildout/openerp-downloads

gunicorn
--------

Gunicorn integration is only supported on OpenERP >= 6.1
This options allow to generate a script to start OpenERP with Gunicorn.
It currently support two values: ``direct`` and ``proxied``

Direct mode
```````````
Direct mode should be used to let Gunicorn serve requests directly::

    gunicorn = direct

Proxied mode
````````````

Use this mode if you plan to run Gunicorn behind a reverse proxy::

    gunicorn = proxied

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

Finally, you can specify the Gunicorn script name with the
``gunicorn_script_name`` option. The configuration file will be named
accordingly.


OpenERP options
---------------

You can define OpenERP options directly from the buildout file.  The OpenERP
configuration files are generated by OpenERP itself in the buildout `etc`
directory during the first buildout run.  You can overwrite these options in
from the recipe section of your buildout.cfg.  The options must be written
using a dotted notation prefixed with the name of the section.  The specified
options will just overwrite the existing options in the corresponding config
files. You don't have to replicate all the options in your buildout.cfg.  If an
option or a section does not exist in the openerp config file, it can be
created from there.

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

Example OpenERP 6.0 buildout
~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Here is a sample buildout with versions specification, 2 OpenERP servers (with
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


Example OpenERP 6.1 buildout
~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Here is a simple example for a stock OpenERP 6.1, with a GTK client, and a
local addon you are developping for a client project

.. note:: with OpenERP 6.1 the web client is natively included in the server as a
    simple module. In that case you don't need to write a separate part for the web
    client, unless that's what you really want to do.

::

    [buildout]
    parts = openerp gtk
    #allow-picked-versions = false
    versions = versions
    find-links = http://download.gna.org/pychart/
    
    [openerp]
    recipe = anybox.recipe.openerp:server
    version = 6.1-1
    addons = local ../path/to/my/local/addons

    options.xmlrpcs = False

    gunicorn = direct

    [gtk]
    recipe = anybox.recipe.openerp:gtkclient
    version = 6.1-1
    
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

Contribute
~~~~~~~~~~
Authors and contributors:

 * Christophe Combelles
 * Georges Racinet

The primary branch is on the launchpad:

 * Code repository and bug tracker: https://launchpad.net/anybox.recipe.openerp
 * PyPI page: http://pypi.python.org/pypi/anybox.recipe.openerp

Please don't hesitate to give feedback and especially report bugs or
ask for new features through launchpad at this URL: https://bugs.launchpad.net/anybox.recipe.openerp/+bugs
