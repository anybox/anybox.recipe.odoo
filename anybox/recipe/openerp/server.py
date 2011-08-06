import os, sys, urllib2, tarfile, setuptools
from zc.buildout.easy_install import install
import zc.recipe.egg

DOWNLOAD_URL = 'http://www.openerp.com/download/stable/source/'
SERVER_FILENAME = 'openerp-server-%s.tar.gz'

class Server(object):

    def __init__(self, buildout, name, options):
        self.buildout, self.name, self.options = buildout, name, options
        self.version = self.options['version']
        self.archive = SERVER_FILENAME % self.version
        self.url = DOWNLOAD_URL + self.archive
        if 'url' in self.options:
            self.url = self.options['url']
            self.archive = self.url.split('/')[-1]

    def install(self):
        os.chdir('parts')

        # download and extract
        if not os.path.exists(self.archive):
            print(u'Downloading OpenERP...')
            open(self.archive, 'w').write(urllib2.urlopen(self.url).read())
            print(u'Extracting OpenERP...')
            tar = tarfile.open(self.archive)
            tar.extractall()
            tar.close()

        # ugly method to retrieve requirements
        os.chdir(self.archive.replace('.tar.gz', ''))
        old_setup = setuptools.setup
        requirements = []
        def new_setup(*args, **kw):
            requirements.extend(kw['install_requires'])
        setuptools.setup = new_setup
        sys.path.insert(0, '.')
        import setup
        _ = sys.path.pop(0)
        setuptools.setup = old_setup

        # install requirements and scripts
        eggs = zc.recipe.egg.Eggs(self.buildout, self.name, self.options)
        eggs.working_set(extra=requirements)
        zc.recipe.egg.Scripts(self.buildout, self.name, self.options).install()

    update = install


