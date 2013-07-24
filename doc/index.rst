.. OpenERP buildout recipe documentation master file, created by
   sphinx-quickstart on Wed Jul 24 18:32:19 2013.
   You can adapt this file completely to your liking, but it should at least
   contain the root `toctree` directive.

OpenERP buildout recipe
=======================

This recipe for `zc.buildout` is a fully featured tool allowing you to
define and deploy quickly
OpenERP installations of any kinds, ranging from development setups to
fully automated production deployments or continuous integration.

Some of its main features include:

* uniformity across OpenERP versions (from 6.0 onwards)
* installation of OpenERP server, GTK client and web client for
  versions that need it.
* retrieval of main software and addons from various sources,
  including the major version control systems
* ability to pinpoint everything for replayability
* management of OpenERP configuration
* dedicated scripts creation for easy integration of external tools,
  such as test launchers
* packaging: creation of self-contained equivalents for easy
  deployment in tightly controlled hosting environmenents.

All these to be considered together with ``zc.buildout``'s general properties,
such as an extensible configuration file format for easy variation or
separation of concerns, native Python distributions installation, and
of course the huge ecosystem of other recipes.

Contents
========

.. toctree::
   :maxdepth: 2
   :glob:

   *

Code documentation
==================

.. toctree::
   :maxdepth: 1
   :glob:

   apidoc/anybox*


Indices and tables
==================

* :ref:`genindex`
* :ref:`modindex`
* :ref:`search`

