import sys
import os

def insert_args(arguments):
    for i, a in enumerate(arguments):
        sys.argv.insert(i+1, a)

def main(starter, conf, openerp_version):
    arguments = ['-c', conf, '--log-level=test', '--stop-after-init']
    if openerp_version.startswith('7.'):
        arguments.append('--test-enable')

    insert_args(arguments)

    os.chdir(os.path.split(starter)[0])
    glob = globals()
    glob['__name__'] = '__main__'
    glob['__file__'] = starter
    execfile(starter, globals())
