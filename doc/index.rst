.. Odoo buildout recipe documentation master file, created by
   sphinx-quickstart on Wed Jul 24 18:32:19 2013.
   You can adapt this file completely to your liking, but it should at least
   contain the root `toctree` directive.

Odoo buildout recipe
=======================

.. note:: if you wish to manage OpenERP/Odoo versions before the
          product rename that occurred for v8, you should go to
          `anybox.recipe.openerp
          <https://pypi.python.org/pypi/anybox.recipe.openerp>`_.

This recipe for `Buildout <https://github.com/buildout/buildout>`_ is
a fully featured tool allowing you to define and deploy quickly
Odoo installations of any kinds, ranging from development setups to
fully automated production deployments or continuous integration.

Some of its main features include:

* installation of Odoo server, uniformly across versions.
* retrieval of main software and addons from various sources,
  including the major version control systems
* ability to pinpoint everything for replayability
* management of Odoo configuration
* dedicated scripts creation for easy integration of external tools,
  such as test launchers
* packaging: creation of self-contained equivalents for easy
  deployment in tightly controlled hosting environmenents.

All these to be considered together with zc.buildout‘s general
properties, such as an extensible configuration file format for easy
variation or separation of concerns, native Python distributions
installation, and of course the huge ecosystem of other recipes.

About this documentation
------------------------

Released *stable* versions of this documentation are uploaded to `pythonhosted
<http://pythonhosted.org/anybox.recipe.odoo>`_.

The full documentation is written with `Sphinx
<http://sphinx-doc.org>`_, built continuously and
uploaded to http://docs.anybox.fr/anybox.recipe.odoo/current by Anybox' public
buildbot.
The Sphinx source tree is to be found under the ``doc`` subdirectory
of this project.

Although this Sphinx documentation started with version 1.8.0, most of
its contents applies to the 1.7 series: features introduced with 1.8
are highlighted, and readers may consult the `changelog on PyPI
<https://pypi.python.org/pypi/anybox.recipe.odoo#changes>`_.

Contents
--------

.. toctree::
   :maxdepth: 2
   :glob:

   first_steps
   configuration
   scripts
   dev_prod_workflow
   contributing
   devnotes/index

Code documentation
------------------

.. toctree::
   :maxdepth: 1
   :glob:

   apidoc/anybox*


Indices and tables
------------------

* :ref:`genindex`
* :ref:`modindex`
* :ref:`search`

