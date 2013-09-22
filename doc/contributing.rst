For contributors
================

Source and tracking
~~~~~~~~~~~~~~~~~~~
The recipe is currently hosted as a launchpad project, under Bazaar
version control: https://launchpad.net/anybox.recipe.openerp

We follow the standard launchpad workflow (bugs, merge requests…).
Code contributors are systematically added to the list of
contributors at the end of the README, unless they explicitely wish
not to (what Launchpad does is obvisouly out of our scope).

There are currently no branch naming rules.

Members of the "Anybox" team have push privileges on the main branches.

Using a development version
~~~~~~~~~~~~~~~~~~~~~~~~~~~

To use a local version of the recipe, you may use the ``develop``
general buildout option::

  [buildout]
  develop = /path/to/anybox.recipe.openerp

To track the latest version of a ``bzr`` branch of the recipe, we find
the
`gp.vcsdevelop <https://pypi.python.org/pypi/gp.vcsdevelop>`_
extension simple and useful. Here's an example (excerpt from
``buildot/recipe-trunk.cfg``)::

  [buildout]
  extensions = gp.vcsdevelop
  vcs-extend-develop = bzr+http://bazaar.launchpad.net/~anybox/anybox.recipe.openerp/trunk#egg=anybox.recipe.openerp
  vcs-update = True

.. note::
  Actually some parts of the recipe are aware of the possible use
  of ``gp.vcsdevelop`` for python dependencies, and special care of it is
  taken in the freeze and extract features. This is known to work even
  for ``zc.buildout`` itself.

Development setup
~~~~~~~~~~~~~~~~~

We recommend "developping" the source code in a virtualenv, together
with ``bzr``. For instance::

  virtualenv recipe-env
  recipe-env/bin/pip install bzr
  recipe-env/bin/bzr branch lp:anybox.recipe.openerp
  cd anybox.recipe.openerp
  python setup.py develop

Coding style
~~~~~~~~~~~~

The recipe follows the same strong code development coding principles
as many other projects:

* Style enforcement : we follow the PEP8 guidelines
* Static analysis with `flake8 <https://pypi.python.org/pypi/flake8>`_
  (combines conveniently `pep8 <https://pypi.python.org/pypi/pep8>`_
  and `pyflakes <https://pypi.python.org/pypi/pyflakes>`_).
* Unit tests : we try and test as much as possible. It is hard to achieve a
  real 100% with a tool that calls so many external processes, but
  this is mitigated by our
  :ref:`continuous integration <continuous_integration>` practice of
  doing real OpenERP installations with the latest revision of the recipe.

Launching static analysis and unit tests
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Install ``nose``, ``flake8`` and, optionally, ``coverage``::

   recipe-env/bin/pip install nose coverage flake8==2.0 \
                      pep8=1.4.6 mccabe==0.2.1 pyflakes==0.7.3 nose


.. note:: we've had problems lately with discrepancies in ``pep8``
          versions, that's why versions of ``flake8`` and its
          dependencies are fixed above. In case of doubt, check what
          the buildbot is actually running.

Run ``flake8`` and the tests::

    cd anybox.recipe.openerp
    flake8 anybox && nosetests anybox --with-doctest

There is also this convenience to run the tests and output a coverage report::

    source ./test-cover


.. _integration tests:

Integration tests
~~~~~~~~~~~~~~~~~

There is a special category of tests: those that need a real OpenERP
instance, built with the recipe, to run.

They are located within the ``tests_with_openerp`` subdirectory and
need to be launched with a launcher script constructed by the recipe.

For example, create a testing buildout like this::

  [openerp]
  # version as you wish
  eggs = nose
  openerp_scripts nosetests command-line-options = -d

Then run ``bin/buildout``, create a database and initialize it. From
the buildout directory::

  createdb test-recipe
  bin/start_openerp -d test-recipe -i base --stop-after-init

You can then run the tests::

  bin/nosetests_openerp -d test-recipe -- /path/to/recipe/branch/tests_with_openerp

Currently, these tests are all about the ``Session`` objects, used in
scripts.

.. note:: you may use a different version of the recipe to build that
          testing buildout. This is anyway what happens if you build
          with your development version, and hack some changes
          afterwards.

          Using a very different version of the recipe could give
          funky results, but you're supposed to know what you're doing
          at this point.


.. _continuous_integration:

Continuous integration
~~~~~~~~~~~~~~~~~~~~~~

Basic builds
------------

Upon each push on the main branches, Anybox' public
buildbot awakes to check the coding style, run the tests and build
this documentation. You may check the status there:

* `trunk builder
  <http://buildbot.anybox.fr/waterfall?show=anybox.recipe.openerp>`_
* `stable builder
  <http://buildbot.anybox.fr/waterfall?show=anybox.recipe.openerp-stable>`_

Actual runs
-----------

Furthermore, this buildbot instance runs `anybox.buildbot.openerp
<https://pypi.python.org/pypi/anybox.buildbot.openerp>`_,
a buildbot configurator for OpenERP installations based on the recipe.

This is used in turn to run high-level integration tests, having the
latest bzr version of the recipe actually install several combinations
of OpenObject server and addons, and run their unit tests.

The configuration is stored in the ``buildbot`` subdirectory of the
recipe trunk branch. It is made of a high level configuration file
(``MANIFEST.cfg``) and buildout configuration files. This buildbot
instance actually aggregates several such configurations.

The corresponding builders are those whose name starts with
``recipe-`` or ``stable-recipe-`` in the `builders list
<http://buildbot.anybox.fr/builders>`_.

.. note:: the `integration tests`_ mentioned above are executed in
          particular during this process, currently in the
          ``recipe-7.0-postgresql-9.2`` builder.

Some builds may appear to be broken because of tests failures been
pushed by upstream in OpenERP itself or in the tested addons, but it's
easy to check whether this is due to a recipe failure or not.

.. note::

   Anybox hardware resources are limited; contributing buildslaves would
   be greatly appreciated.


