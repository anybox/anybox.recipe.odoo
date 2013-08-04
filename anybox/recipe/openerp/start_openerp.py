import sys
import os


def main(starter, conf, version=None):
    sys.argv.insert(1, '-c')
    sys.argv.insert(2, conf)
    os.chdir(os.path.split(starter)[0])

    if version == (5, 0):
        from . import patch_openerp_v5  # noqa

    glob = globals()
    glob['__name__'] = '__main__'
    glob['__file__'] = starter
    execfile(starter, globals())
