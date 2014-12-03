from zc.buildout import UserError
from .base import UpdateError  # noqa
from .hg import HgRepo
from .bzr import BzrBranch
from .svn import SvnCheckout
from .git import GitRepo

SUPPORTED = {}

SUPPORTED['hg'] = HgRepo
SUPPORTED['bzr'] = BzrBranch
SUPPORTED['git'] = GitRepo
SUPPORTED['svn'] = SvnCheckout


def repo(vcs_type, target_dir, url, **options):
    cls = SUPPORTED.get(vcs_type)
    if cls is None:
        raise UserError("Unsupported VCS type: %r" % vcs_type)
    return cls(target_dir, url, **options)


def get_update(vcs_type, target_dir, url, revision, **options):
    """General entry point."""
    return repo(vcs_type, target_dir, url, **options)(revision)
