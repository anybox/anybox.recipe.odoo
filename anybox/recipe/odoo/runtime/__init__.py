"""
Runtime
=======

This subpackage provides encapsulations and entry points for the application
itself:

* the ``session`` module features the supporting objects for "OpenERP scripts"
  and the dedicated python interpreter.
* the ``start_openerp`` and ``test_openerp`` modules are the entry points for
  the main startup scripts.

This architecture is meant in particular to provide stability and uniformity
accross OpenERP major versions, so that the recipe can be leveraged by
automated deploymnent tools and continuous integration systems.
"""

_imported_addons = set()


def already_imported(module_name):
    """Convenience to help some OpenERP modules to avoid been imported twice.

    Each call of this function returns a boolean indicated whether the
    specified module was already in the ``imported_addons`` registry and add it
    inconditionnally.

    Thus caller code is expected to import the module right away if the
    return value was False.
    """
    name = module_name.rsplit('.', 1)[-1]
    if name in _imported_addons:
        return True
    _imported_addons.add(name)
    return False


def clear_import_registry():
    _imported_addons.clear()
