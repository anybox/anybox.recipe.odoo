import os
import re
from contextlib import contextmanager

class WorkingDirectoryKeeper(object):
    """A context manager to get back the working directory as it was before."""

    active = False

    def __enter__(self):
        if self.active:
            raise RuntimeError("Already in a working directory keeper !")
        self.wd = os.getcwd()
        self.active = True

    def __exit__(self, *exc_args):
        os.chdir(self.wd)
        self.active = False

working_directory_keeper = WorkingDirectoryKeeper()

@contextmanager
def use_or_open(provided, path, *open_args):
    """A context manager to use an open file if not None or open one.

    Useful for code that should be unit-testable, but work on a default file if
    None is passed.
    """
    if provided is not None:
        yield provided
    else:
        with open(path, *open_args) as f:
            yield f


NIGHTLY_VERSION_RE = re.compile(r'(\d+)[.](\d+)-(\d+-\d+)$')

MAJOR_VERSION_RE = re.compile(r'(\d+)[.](\d+)')


def major_version(version_string):
    """The least common denominator of OpenERP versions : two numbers.

    OpenERP version numbers are a bit hard to compare if we consider nightly
    releases, bzr versions etc. It's almost impossible to compare them without
    an a priori knowledge of release dates and revisions.

    Beware, the packaging script does funny things, such as labeling current
    nightlies as 6.2-date-time whereas version_info is (7, 0, 0, ALPHA)
    We can in recipe code check for >= (6, 2), that's not a big issue.
    """

    m = MAJOR_VERSION_RE.match(version_string)
    if m is not None:
        return tuple(int(m.group(i)) for i in (1,2))

def mkdirp(path):
    """Same as mkdir -p."""
    if not os.path.exists(path):
        parent, name = os.path.split(path)
        mkdirp(parent)
        os.mkdir(path)
