"""VCS tests: Subversion."""

import os
import subprocess
from ..testing import VcsTestCase
from ..svn import SvnCheckout


class SvnTestCase(VcsTestCase):

    def create_src(self):
        os.chdir(self.src_dir)
        subprocess.check_call(['svnadmin', 'create', 'src-repo'])
        self.src_repo = os.path.join(self.src_dir, 'src-repo')
        self.src_repo = 'file://' + self.src_repo

        tmp_checkout = os.path.join(self.src_dir, 'tmp_checkout')
        subprocess.call(['svn', 'checkout', self.src_repo, tmp_checkout])

        os.chdir(tmp_checkout)
        f = open('tracked', 'w')
        f.write("first" + os.linesep)
        f.close()
        subprocess.call(['svn', 'add', 'tracked'])
        subprocess.call(['svn', 'commit', '-m', 'initial commit'])
        f = open('tracked', 'w')
        f.write("last" + os.linesep)
        f.close()
        subprocess.call(['svn', 'commit', '-m', 'last version'])

    def test_checkout(self):
        """Svn clone."""
        target_dir = os.path.join(self.dst_dir, "Mycheckout")
        SvnCheckout(target_dir, self.src_repo)('head')

        self.assertTrue(os.path.isdir(target_dir))
        f = open(os.path.join(target_dir, 'tracked'))
        lines = f.readlines()
        f.close()
        self.assertEquals(lines[0].strip(), 'last')
