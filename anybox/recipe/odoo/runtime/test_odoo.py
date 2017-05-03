import sys
import os


def insert_args(arguments):
    for i, a in enumerate(arguments):
        sys.argv.insert(i+1, a)


def main(starter, conf, version=()):
    if version >= (6, 0):
        log_level = 'test'
    else:
        log_level = 'info'
    arguments = ['-c', conf, '--log-level', log_level, '--stop-after-init']
    if version >= (7, 0):
        arguments.append('--test-enable')

    insert_args(arguments)

    os.chdir(os.path.split(starter)[0])
    glob = globals()
    glob['__name__'] = '__main__'
    glob['__file__'] = starter
    execfile(starter, globals())
