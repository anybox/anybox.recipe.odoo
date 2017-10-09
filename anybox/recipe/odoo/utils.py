import os
import sys
import re
import subprocess
from contextlib import contextmanager
try:
    from ConfigParser import DuplicateSectionError  # Python 2
except ImportError:
    from configparser import DuplicateSectionError  # Python 3
import logging
logger = logging.getLogger(__name__)


MAJOR_VERSION_RE = re.compile(r'(\d+)[.](saas~|)(\d*)(\w*)')


class WorkingDirectoryKeeper(object):
    """A context manager to get back the working directory as it was before.

    If you want to stack working directory keepers, you need a new instance
    for each stage.
    """

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


def major_version(version_string):
    """The least common denominator of Odoo versions : two numbers.

    Odoo version numbers are a bit hard to compare if we consider nightly
    releases, bzr versions etc. It's almost impossible to compare them without
    an a priori knowledge of release dates and revisions.

    Here are some examples::

       >>> major_version('1.2.3-foo.bar')
       (1, 2)
       >>> major_version('6.1-20121003-233130')
       (6, 1)
       >>> major_version('7.0alpha')
       (7, 0)

    Beware, the packaging script does funny things, such as labeling current
    nightlies as 6.2-date-time whereas version_info is (7, 0, 0, ALPHA)
    We can in recipe code check for >= (6, 2), that's not a big issue.

    Regarding Odoo saas releases (e.g. 7.saas~1) that are short-lived stable
    versions between two "X.0" LTS releases, the 'saas~' argument before the
    minor version number is stripped. For instance::

       >>> major_version('7.saas~3')
       (7, 3)

    """

    m = MAJOR_VERSION_RE.match(version_string)

    if m is None:
        raise ValueError("Unparseable version string: %r" % version_string)

    major = int(m.group(1))
    minor = m.group(3)

    try:
        return major, int(minor)
    except TypeError:
        raise ValueError(
            "Unrecognized second version segment in %r" % version_string)


def is_object_file(filename):
    """True if given filename is a python object file."""
    return filename.endswith('.pyc') or filename.endswith('.pyo')


def clean_object_files(directory):
    """Recursively remove object files in given directory.

    Also remove resulting empty directories.
    """
    dirs_to_remove = []
    for dirpath, dirnames, filenames in os.walk(directory, topdown=False):
        to_delete = [os.path.join(dirpath, f)
                     for f in filenames if is_object_file(f)]
        if not dirnames and len(to_delete) == len(filenames):
            dirs_to_remove.append(dirpath)
        for p in to_delete:
            try:
                os.unlink(p)
            except:
                logger.exception("Error attempting to unlink %r. "
                                 "Proceeding anyway.", p)
    for d in dirs_to_remove:
        try:
            os.rmdir(d)
        except:
            logger.exception("Error attempting to rmdir %r",
                             "Proceeding anyway.", p)


def check_output(*popenargs, **kwargs):
    r"""Backport of subprocess.check_output from python 2.7.

    Example (this doctest would be more readable with ELLIPSIS, but
    that's good enough for today):

    >>> out = check_output(["ls", "-l", "/dev/null"])
    >>> out.startswith('crw-rw-rw')
    True

    The stdout argument is not allowed as it is used internally.
    To capture standard error in the result, use stderr=STDOUT.

    >>> os.environ['LC_ALL'] = 'C'  # for uniformity of error msg
    >>> err = check_output(["/bin/sh", "-c",
    ...               "ls -l non_existent_file ; exit 0"],
    ...              stderr=subprocess.STDOUT)
    >>> err.strip().endswith("No such file or directory")
    True
    """

    if sys.version_info >= (2, 7):
        return subprocess.check_output(*popenargs, **kwargs).decode('ascii')
    if 'stdout' in kwargs:
        raise ValueError('stdout argument not allowed, it will be overridden.')

    process = subprocess.Popen(stdout=subprocess.PIPE, *popenargs, **kwargs)
    output, unused_err = process.communicate()
    retcode = process.poll()
    if retcode:
        cmd = kwargs.get("args")
        if cmd is None:
            cmd = popenargs[0]
        # in python 2.6, CalledProcessError.__init__ does not have output kwarg
        exc = subprocess.CalledProcessError(retcode, cmd)
        exc.output = output
        raise exc
    return output


INLINE_COMMENT_REGEXP = re.compile(r'\s;|^;')


def option_splitlines(opt_val):
    r"""Split a multiline option value.

    This function performs stripping of whitespaces and allows comments as
    `ConfigParser <http://docs.python.org/2/library/configparser.html>`_ would
    do. Namely:

    * a line starting with a hash is a comment. This is already taken care of
      by ``zc.buildout`` parsing of the configuration file.

      :mod:`ConfigParser` does not apply this rule to the case where the hash
      is after some leading whitespace (e.g, line-continuation
      indentation) as in this example::

          [foo]
          bar = line1
            line2
          # this is a comment
            # this is not a comment, and will appear in 'bar' value

      Therefore this function does not have to perform anything with respect to
      hash-comments.

    * everything after a semicolon following a whitespace is a comment::

          [foo]
          bar = line1
                line2 ;this is a comment

    :param basestring opt_val: the raw option value
    :returns: tuple of strings

    doctests (less readable than examples above, but more authoritative)::

        >>> option_splitlines('line1\n  line2 ;this is a comment\n  line3')
        ('line1', 'line2', 'line3')
        >>> option_splitlines('l1\n; inline comment from beginning\n  line3')
        ('l1', 'line3')
        >>> option_splitlines('l1\n; inline comment from beginning\n  line3')
        ('l1', 'line3')
        >>> option_splitlines('l1\n  ; disappears after stripping \n  line3')
        ('l1', 'line3')
        >>> option_splitlines('line1\n\n')
        ('line1',)
        >>> option_splitlines('')
        ()

    The return value is guaranteed not to be a single string::

        >>> option_splitlines('single')
        ('single',)

    For convenience, ``None`` is accepted::

        >>> option_splitlines(None)
        ()

    """
    if opt_val is None:
        return ()

    lines = opt_val.splitlines()
    return tuple(l for l in (option_strip(line) for line in lines)
                 if l)


def option_strip(opt_val):
    """Same as :func:`option_splitlines` for a single line.

    >>> option_strip("   hey, we have ; a comment")
    'hey, we have'
    >>> option_strip(None) is None
    True
    """
    if opt_val is not None:
        return INLINE_COMMENT_REGEXP.split(opt_val, 1)[0].strip()


def total_seconds(td):
    """Uniformity backport of :meth:`datetime.timedelta.total_seconds``

    :param td: a :class:`datetime.timedelta` instance
    :returns: the number of seconds in ``tdelta``

    The implementation for Python < 2.7 is taken from the
    `standard library documentation
    <https://docs.python.org/2.7/library/datetime.html>`_
    """
    if sys.version_info >= (2, 7):
        return td.total_seconds()

    return ((td.microseconds +
             (td.seconds + td.days * 24 * 3600) * 1e6) / 10**6)


def conf_ensure_section(conf, section):
    try:
        conf.add_section(section)
    except DuplicateSectionError:
        pass


def next(iterator):
    """ Python2 compatibility of iterators """
    return iterator.next()
