import sys
import os


def insert_args(arguments):
    for i, a in enumerate(arguments):
        sys.argv.insert(i+1, a)


def main(starter, conf, version=()):
    arguments = ['-c', conf, '--log-level=test', '--stop-after-init']
    if version >= (7, 0):
        arguments.append('--test-enable')

    insert_args(arguments)

    if version == (5, 0):
        from . import patch_openerp_v5  # noqa

    os.chdir(os.path.split(starter)[0])
    glob = globals()
    glob['__name__'] = '__main__'
    glob['__file__'] = starter
    execfile(starter, globals())
