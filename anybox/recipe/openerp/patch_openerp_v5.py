"""Enable multiple addons paths in OpenERP 5.0.x

This is done as monkey patch, because the recipe must take care of not
modifying the source, so that release scripts don't refuse releasing the
buildout directory.

As of this writing, version 5.0 has been frozen for long already.
"""

import sys
import os


def do_patch():

    import addons

    # reverting side effects of addons import, and storing our addons path
    if addons.ad is not None:
        addons.buildout_addons_paths = [
            p.strip() for p in addons.tools.config['addons_path'].split(',')]
        sys.path.remove(addons.ad)
        if addons._ad != addons.ad:
            sys.path.remove(addons._ad)
        addons.ad = None

    def get_module_path(module, downloaded=False):
        """Return the path of the given module.

        """

        logger, netsvc = addons.logger, addons.netsvc
        for path in addons.buildout_addons_paths:
            module_path = os.path.join(path, module)
            if (os.path.exists(module_path)
                    or os.path.exists(module_path + '.zip')):
                logger.notifyChannel('init', netsvc.LOG_INFO,
                                     'module %r: found at %s' % (module,
                                                                 module_path))

                return module_path

        if downloaded:
            return os.path.join(addons._ad, module)
        logger.notifyChannel('init', netsvc.LOG_WARNING,
                             'module %r: module not found' % (module,))
        return False

    def get_modules():
        """Returns the list of module names
        """
        def listdir(dir):
            def clean(name):
                name = os.path.basename(name)
                if name[-4:] == '.zip':
                    name = name[:-4]
                return name

            def is_really_module(name):
                name = os.path.join(dir, name)
                return os.path.isdir(name) or addons.zipfile.is_zipfile(name)

            return map(clean, filter(is_really_module, os.listdir(dir)))

        return list(set(m for path in addons.buildout_addons_paths
                        for m in listdir(path)))

    import imp
    import zipimport

    def register_class(m):
        """
        Register module named m, if not already registered

        Only modification from the original function is mentionned as comment.
        """

        logger, netsvc = addons.logger, addons.netsvc

        def log(e):
            mt = isinstance(e, zipimport.ZipImportError) and 'zip ' or ''
            msg = "Couldn't load %smodule %s" % (mt, m)
            logger.notifyChannel('init', netsvc.LOG_CRITICAL, msg)
            logger.notifyChannel('init', netsvc.LOG_CRITICAL, e)

        if m in addons.loaded:
            return

        logger.notifyChannel('init', netsvc.LOG_INFO,
                             'module %r: registering objects' % m)
        mod_path = get_module_path(m)

        try:
            zip_mod_path = mod_path + '.zip'
            if not os.path.isfile(zip_mod_path):
                # line below modified
                fm = imp.find_module(m, addons.buildout_addons_paths)
                try:
                    imp.load_module(m, *fm)
                finally:
                    if fm[0]:
                        fm[0].close()
            else:
                zimp = zipimport.zipimporter(zip_mod_path)
                zimp.load_module(m)
        except Exception, e:
            log(e)
            raise
        else:
            addons.loaded.append(m)

    addons.get_module_path = get_module_path
    addons.get_modules = get_modules
    addons.register_class = register_class
    import tools.misc

    orig_file_open = tools.misc.file_open

    def file_open(name, mode="r", subdir='addons', pathinfo=False):
        """Modified version for calls after direct join of module names.

        For example, this can be seen in ``addons.load_module_graph()``
           fp = tools.file_open(opj(m, filename))

        Found it simpler (and necessary, given there were references to
        addons_path and root_path) to correct from here.

        The original one does try and replace subpaths by zip files if
        some are found. We simply call it back to avoid duplicating this
        (in the same way it's already doing after subdir related resolutions).
        """

        if name.replace(os.path.sep, '/').startswith('addons/'):
            subdir = 'addons'
            name = name[7:]

        # First try to locate in addons_path
        if subdir:  # remember that the default value is 'addons'
            subdir2 = subdir
            if subdir2.replace(os.path.sep, '/').startswith('addons/'):
                subdir2 = subdir2[7:]

            subdir2 = (subdir2 != 'addons' or None) and subdir2
            if os.path.isabs(name):
                fn = name
            elif subdir2 is None:
                # first segment is necessary the module name
                fn = addons.get_module_resource(*name.split(os.path.sep, 1))

            try:
                fn = os.path.normpath(fn)
                # subdir=None will skip this override's equivalent in
                # original code (leading to zip handling etc)
                fo = file_open(fn, mode=mode, subdir=None, pathinfo=pathinfo)
                if pathinfo:
                    return fo, fn
                return fo
            except IOError:
                pass

        rtp = os.path.normcase(os.path.abspath(tools.config['root_path']))
        if subdir:
            name = os.path.join(rtp, subdir, name)
        else:
            name = os.path.join(rtp, name)

        name = os.path.normpath(name)
        return orig_file_open(name, subdir=None, pathinfo=pathinfo)

    tools.misc.file_open = tools.file_open = file_open
