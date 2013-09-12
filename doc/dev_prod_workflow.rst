Full development to production example
=======================================

In this example, we present one way of organizing a project, to
provide easy to install development setups, continuous integration and
production deployments.

Please read this as a pattern among many others. If you decide to base
your development process on it, you'll have to adapt it to your team's
practice anyway.

Common setup
~~~~~~~~~~~~

Developer's setup
~~~~~~~~~~~~~~~~~
Here we add private read-write access to version control systems.
We need to version the buildout itself, and make decisions about which
addons will be under active development within that project.

At this point, asking a developer to work on the project is as simple
as providing the main URL to get the buildout from VCS.

Release and packaging
~~~~~~~~~~~~~~~~~~~~~
Use of ``freeze-to``, ``extract-downloads-to``, and production of a tarball.

Deployment with a server-local configuration file
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
You may decide to track the local files with a VCS, too, but it's
preferable to keep it distinct from the main code base.

