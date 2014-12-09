OpenERP buildout recipe
=======================
This recipe for `Buildout <https://github.com/buildout/buildout>`_ is
a fully featured tool allowing you to define and deploy quickly
OpenERP installations of any kinds, ranging from development setups to
fully automated production deployments or continuous integration.

Some of its main features include:

* uniformity across OpenERP versions (from 5.0 onwards)
* installation of OpenERP server and, if meaningful, GTK and web clients.
* retrieval of main software and addons from various sources,
  including the major version control systems
* ability to pinpoint everything for replayability
* management of OpenERP configuration
* dedicated scripts creation for easy integration of external tools,
  such as test launchers
* packaging: creation of self-contained equivalents for easy
  deployment in tightly controlled hosting environmenents.

All these to be considered together with zc.buildout‘s general
properties, such as an extensible configuration file format for easy
variation or separation of concerns, native Python distributions
installation, and of course the huge ecosystem of other recipes.

The `full documentation
<http://pythonhosted.org/anybox.recipe.openerp>`_
is written with `Sphinx
<http://sphinx-doc.org>`_, built continuously and
uploaded to http://docs.anybox.fr/anybox.recipe.openerp by Anybox' public
buildbot.
The Sphinx source tree is to be found under the ``doc`` subdirectory
of this project.

The latest released version of the documentation is uploaded to PyPI
alongside with the package. See `PyPIDocumentationHosting
<https://wiki.python.org/moin/PyPiDocumentationHosting>`_ for details.

Bug reports and Feedback
~~~~~~~~~~~~~~~~~~~~~~~~
Please don't hesitate to give feedback and especially report bugs or
ask for new features through launchpad at this URL:
https://bugs.launchpad.net/anybox.recipe.openerp/+bugs

Useful links
~~~~~~~~~~~~

* Code repository and bug tracker: https://launchpad.net/anybox.recipe.openerp
* PyPI page: http://pypi.python.org/pypi/anybox.recipe.openerp
* Main documentation: http://docs.anybox.fr/anybox.recipe.openerp


Contributors information
~~~~~~~~~~~~~~~~~~~~~~~~

See `the latest version of the contributors documentation
<http://docs.anybox.fr/anybox.recipe.openerp/trunk/contributing.html>`_.


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
