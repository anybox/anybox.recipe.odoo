Odoo buildout recipe
====================

.. image:: https://badge.fury.io/py/anybox.recipe.odoo.svg?
    :target: http://badge.fury.io/py/anybox.recipe.odoo
.. image:: https://travis-ci.org/anybox/anybox.recipe.odoo.svg?branch=master
    :target: https://travis-ci.org/anybox/anybox.recipe.odoo
.. image:: https://coveralls.io/repos/anybox/anybox.recipe.odoo/badge.svg?branch=master
    :target: https://coveralls.io/r/anybox/anybox.recipe.odoo?branch=master
.. image:: https://img.shields.io/badge/licence-AGPL--3-blue.svg
    :alt: License: AGPL-3

This recipe for `Buildout <https://github.com/buildout/buildout>`_ is
a fully featured tool allowing you to define and deploy quickly
Odoo installations of any kinds, starting from the 8.0 series, and
ranging from development setups to
fully automated production deployments or continuous integration.

.. note:: For older Odoo versions (which was known as "OpenERP" at the
          time), please use ``anybox.recipe.openerp``, that you'll
          find also on `PyPI
          <https://pypi.python.org/pypi/anybox.recipe.openerp>`_
          and `GitHub <https://github.com/anybox/anybox.recipe.openerp>`_.

Some of its main features include:

* uniformity across Odoo versions (from 8.0 onwards)
* installation of Odoo server
* retrieval of main software and addons from various sources,
  including the major version control systems
* ability to pinpoint everything for replayability
* management of Odoo configuration
* dedicated scripts creation for easy integration of external tools,
  such as test launchers
* packaging: creation of self-contained equivalents for easy
  deployment in tightly controlled hosting environmenents.

All these to be considered together with Buildout‘s general
properties, such as an extensible configuration file format for easy
variation or separation of concerns, native Python distributions
installation, and of course the huge ecosystem of other recipes.

Documentation
~~~~~~~~~~~~~

The `full documentation
<http://pythonhosted.org/anybox.recipe.odoo>`_
is written with `Sphinx
<http://sphinx-doc.org>`_, built continuously and
uploaded to http://docs.anybox.fr/anybox.recipe.odoo by Anybox' public
buildbot.
The Sphinx source tree is to be found under the ``doc`` subdirectory
of this project.

The latest released version of the documentation is uploaded to PyPI
alongside with the package. See `PyPIDocumentationHosting
<https://wiki.python.org/moin/PyPiDocumentationHosting>`_ for details.

Bug reports and Feedback
~~~~~~~~~~~~~~~~~~~~~~~~
Please don't hesitate to give feedback and especially report bugs or
ask for new features on GitHub:
https://github.com/anybox/anybox.recipe.odoo

Useful links
~~~~~~~~~~~~

* PyPI page: http://pypi.python.org/pypi/anybox.recipe.odoo
* Main documentation: http://docs.anybox.fr/anybox.recipe.odoo
* Code repository and bug tracker: https://github.com/anybox/anybox.recipe.odoo


Contributors information
~~~~~~~~~~~~~~~~~~~~~~~~

See `the latest version of the contributors documentation
<http://docs.anybox.fr/anybox.recipe.odoo/current/contributing.html>`_.


Credits
~~~~~~~

Authors:

 * Christophe Combelles
 * Georges Racinet

Contributors:

 * Jean-Sébastien Suzanne
 * Yannick Vaucher
 * Jacques-Etienne Baudoux
 * Laurent Mignon
 * Leonardo Pistone
 * Stefan Rijnhart
 * Stéphane Bidoul
 * Sebastian Kennedy
 * Laetitia Gangloff
 * Sandy Carter
 * Holger Brunn
 * Leonardo Rochael Almeida
 * Alessio Gerace
