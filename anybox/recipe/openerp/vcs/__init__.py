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


def get_update(vcs_type, target_dir, url, revision, **options):
    """General entry point."""
    cls = SUPPORTED.get(vcs_type)
    if cls is None:
        raise ValueError("Unsupported VCS type: %r" % vcs_type)

    # case of standalon addon (see launchpad #1012899)
    target_dir = cls.fix_target(target_dir)
    cls(target_dir, url, **options)(revision)
