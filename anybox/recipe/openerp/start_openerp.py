import sys
import os
from . import patch_openerp_v5


def insert_args(arguments):
    for i, a in enumerate(arguments):
        sys.argv.insert(i+1, a)


def main(starter, conf, version=None, just_test=False):
    arguments = ['-c', conf]

    if just_test:
        arguments.extend(('--log-level',
                          'test' if version >= (6, 0) else 'info',
                          '--stop-after-init'))

        if version >= (7, 0):
            arguments.append('--test-enable')

    insert_args(arguments)

    if version == (5, 0):
        patch_openerp_v5.do_patch()

    os.chdir(os.path.split(starter)[0])
    glob = globals()
    glob['__name__'] = '__main__'
    glob['__file__'] = starter
    execfile(starter, globals())
