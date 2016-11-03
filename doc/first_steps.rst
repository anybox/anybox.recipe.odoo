First steps
===========


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
dependency eggs of Odoo. You can do this by yourself with your system or
Linux distribution.

Or if you're using a Debian based distribution, we provide a single
dependency package you can use to install all dependencies in one shot:

Add the following line in your ``/etc/apt/sources.list``::

  deb http://apt.anybox.fr/openerp common main

If you don't want your system to complain about non-signed packages,
have it accept the signing key, e.g. by issuing::

  sudo apt-key adv --keyserver hkp://subkeys.pgp.net --recv-keys 0xE38CEB07

(sometimes, the key server is too busy, you may need to wait a few
minutes and try again)

Install the dependency package::

  $ sudo aptitude update
  $ sudo aptitude install openerp-server-system-build-deps

You can uninstall this package with ``aptitude`` after the build to
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
Bootstrapping the buildout consists in creating the basic structure of
the buildout, and installing buildout itself in the directory.
Once it's been done, everything is under tight control.

The easiest way to bootstrap is to use the ``bootstrap.py`` script::

  $ wget https://raw.github.com/buildout/buildout/master/bootstrap/bootstrap.py

As of zc.buildout version 2.2, strong isolation from the system-wide Python
installation has been abandoned because of its redundancy with the
very popular `virtualenv <https://pypi.python.org/pypi/virtualenv>`_.
Besides, the bootstrap actually fails if a version of
setuptools older than 0.7 is present system-wide (happens easily
enough at the time of this writing).

The universal current way of doing is therefore to start from a
virtualenv *without setuptools*. For virtualenv >= 1.9, just do::

  $ virtualenv sandbox --no-setuptools

For older versions of virtualenv::

  $ virtualenv sandbox
  $ sandbox/bin/pip uninstall setuptools pip

.. note:: to install virtualenv.

          * Debian family: sudo aptitude install python-virtualenv
          * Redhat/Fedora/CenOS family: sudo yum install python-virtualenv

Finally, perform the bootstrap with the virtualenv's Python::

  $ sandbox/bin/python bootstrap.py

.. warning:: ``boostrap.py`` will fail if you don't already have a valid
             ``buildout.cfg`` file. Don't hesitate over options, you
             can bootstrap with a really minimal one and tweak it
             later.

From now on, all buildout related operations, including Odoo
startup script, custom scripts will be protected by the virtualenv.

.. note:: nothing, not even ``zc.buildout`` actually gets installed by
          buildout in such a virtualenv.
          It's *totally safe* if you're managing several buildouts to
          share a single such virtualenv among all of them.

.. note:: since the bootstrap operation is so sensitive, we recommend
          package managers to include the precise ``bootstrap.py`` in
          their distributed buildout, and to bundle a future-proof
          shell script, using options such as ``-v``.


Running the build
-----------------
This is the day-to-day operation. Just run ::

  $ bin/buildout

And rerun to apply any changes you could later make to ``buildout.cfg``.

Starting Odoo
-------------

Just run ::

  $ bin/start_openerp

.. _example 7.0:

Example OpenERP 7.0 buildouts
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
This example builds the latest nightly OpenERP 7 version.
Note how most Python distribution versions are pinned.

While not mandatory, version pinning is an
important part of the buildout culture. Note also how even ``zc.buildout``
and the current recipe versions can be pinned::

  [buildout]
  parts = openerp
  versions = versions
  find-links = http://download.gna.org/pychart/

  [openerp]
  recipe = anybox.recipe.openerp[bzr]:server
  version = nightly 7.0 latest

  [versions]
  setuptools = 1.1.0
  zc.buildout = 2.2.1
  zc.recipe.eggs = 2.0.0
  anybox.recipe.openerp = 1.7.1
  babel = 0.9.6
  Pillow = 1.7.1
  pywebdav = 0.9.4.1
  PyXML = 0.8.4
  pyyaml = 3.10
  werkzeug = 0.8.3
  zsi = 2.0-rc3
  feedparser = 5.1.1
  gdata = 2.0.16
  lxml = 2.3.3
  psycopg2 = 2.4.4
  pydot = 1.0.28
  pyparsing = 1.5.6
  python-dateutil = 1.5
  python-ldap = 2.4.9
  python-openid = 2.2.5
  pytz = 2012b
  vatnumber = 1.0
  vobject = 0.8.1c
  xlwt = 0.7.3

Of course, installing the latest nightly release provided by Odoo
is not really interesting. The flexibility is.

Here's an example with the latest versions of the 7.0 Bazaar branches
on Launchpad as lightweight checkouts (to avoid hour long downloads).
We don't repeat the ``buildout`` and ``versions`` sections::

  [openerp]
  recipe = anybox.recipe.openerp[bzr]:server
  version = bzr lp:openobject-server/7.0 openerp-7.0 last:1 bzr-init=lightweight-checkout
  addons = bzr lp:openobject-addons/7.0 addons-7.0 last:1 bzr-init=lightweight-checkout
           bzr lp:openerp-web/7.0 addons-web-7.0 last:1 subdir=addons bzr-init=lightweight-checkout

Now imagine how easily one can switch branches and redistribute a
ready-to-run buildout on some dedicated support branch, Git mirrors, etc.

The next example is on 6.1 and demonstrates both how to add specific addons
directories, and how uniform it is.

.. _example 6.1:

Example OpenERP 6.1 buildout with a custom addon
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Here is a very simple example for a latest OpenERP 6.1 nightly and a
custom addon hosted on Bitbucket::

    [buildout]
    parts = openerp 
    versions = versions
    find-links = http://download.gna.org/pychart/
    
    [openerp]
    recipe = anybox.recipe.openerp:server
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


Example OpenERP 6.0 buildout (server and clients)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

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
    recipe = anybox.recipe.openerp[bzr]:server
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

Continuously tested examples
~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Other examples are available in the ``buildbot`` subdirectory of the
source distribution archive of this recipe (the ``tar.gz`` file that
can be downloaded `from the PyPI
<http://pypi.python.org/pypi/anybox.recipe.openerp>`_), and are
continuously tested in the
`anybox buildbot <http://buildbot.anybox.fr/>`_ which is powered by
`anybox.buildbot.openerp
<http://pypi.python.org/pypi/anybox.buildbot.openerp>`_.

See also :ref:`continuous_integration` for more details about these
tested examples.

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

