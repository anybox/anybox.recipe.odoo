import os
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

