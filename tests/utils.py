from contextlib import contextmanager
from functools import partial, wraps
from unittest import mock
import copy
import getpass
import os
import re
import shutil
import six
import sys
import tempfile

import pytest

from fabric.state import env, output
from fabric.sftp import SFTP
from fabric.network import to_dict

from server import PORT, PASSWORDS, USER, HOST
from mock_streams import mock_streams


class FabricTest(object):
    """
    Base class which wipes state.env between tests and provides file helpers.
    """
    def setup_method(self, method):
        # Copy env, output for restoration in teardown
        self.previous_env = copy.deepcopy(env)
        # Deepcopy doesn't work well on AliasDicts; but they're only one layer
        # deep anyways, so...
        # NOTE: list() is required. On Python 2 dict.items() returned a list
        # (i.e. a snapshot); on Python 3 it returns a live view, so without
        # the copy this "saved" state tracks every change made during the test
        # and teardown_method restores nothing. Tests which flip output flags
        # (e.g. TestNetwork._prompt_display) then leak into later tests.
        self.previous_output = list(output.items())
        # Allow hooks from subclasses here for setting env vars (so they get
        # purged correctly in teardown())
        self.env_setup()
        # Temporary local file dir
        self.tmpdir = tempfile.mkdtemp()

    def set_network(self):
        env.update(to_dict('%s@%s:%s' % (USER, HOST, PORT)))

    def env_setup(self):
        # Set up default networking for test server
        env.disable_known_hosts = True
        self.set_network()
        env.password = PASSWORDS[USER]
        # Command response mocking is easier without having to account for
        # shell wrapping everywhere.
        env.use_shell = False

    def teardown_method(self, method):
        env.clear() # In case tests set env vars that didn't exist previously
        env.update(self.previous_env)
        output.update(self.previous_output)
        shutil.rmtree(self.tmpdir)

    def path(self, *path_parts):
        return os.path.join(self.tmpdir, *path_parts)

    def mkfile(self, path, contents):
        dest = self.path(path)
        with open(dest, 'w') as fd:
            fd.write(contents)
        return dest

    def exists_remotely(self, path):
        return SFTP(env.host_string).exists(path)

    def exists_locally(self, path):
        return os.path.exists(path)


@contextmanager
def password_response(password, times_called=None, silent=True):
    """
    Context manager which patches ``getpass.getpass`` to return ``password``.

    ``password`` may be a single string or an iterable of strings:

    * If single string, given password is returned every time ``getpass`` is
      called.
    * If iterable, iterated over for each call to ``getpass``, after which
      ``getpass`` will error.

    If ``times_called`` is given, ``getpass`` must have been called exactly
    that many times by the end of the block. Specifying ``times_called``
    alongside an iterable ``password`` list is unsupported.

    If ``silent`` is True, no prompt will be printed to ``sys.stderr``.
    """
    # Assume stringtype or iterable, turn into mutable iterable
    if isinstance(password, six.string_types):
        passwords = [password]
    else:
        passwords = list(password)

    def respond(prompt='', stream=None):
        # Optional echoing of prompt to mimic real behavior of getpass
        # NOTE: also echo a newline if the prompt isn't a "passthrough" from
        # the server (as it means the server won't be sending its own newline
        # for us).
        if not silent and stream is not None:
            stream.write(prompt + ("\n" if prompt != " " else ""))
        # A lone password answers every prompt; a list is consumed one prompt
        # at a time and running off the end is an error, as it means the code
        # under test asked more times than the test said it would.
        index = respond.calls
        respond.calls += 1
        if len(passwords) == 1:
            return passwords[0]
        try:
            return passwords[index]
        except IndexError:
            raise AssertionError(
                "getpass was called %s time(s), but only %s password(s) were "
                "given" % (index + 1, len(passwords)))
    respond.calls = 0

    with mock.patch.object(getpass, 'getpass', side_effect=respond) as fake:
        yield fake
        if times_called is not None:
            eq_(times_called, fake.call_count)


def _assert_contains(needle, haystack, invert):
    matched = re.search(needle, haystack, re.M)
    if (invert and matched) or (not invert and not matched):
        raise AssertionError("r'%s' %sfound in '%s'" % (
            needle,
            "" if invert else "not ",
            haystack
        ))

assert_contains = partial(_assert_contains, invert=False)
assert_not_contains = partial(_assert_contains, invert=True)


def line_prefix(prefix, string):
    """
    Return ``string`` with all lines prefixed by ``prefix``.
    """
    return "\n".join(prefix + x for x in string.splitlines())


def eq_(result, expected, msg=None):
    """
    Shadow of the Nose builtin which presents easier to read multiline output.
    """
    params = {'expected': expected, 'result': result}
    aka = """

--------------------------------- aka -----------------------------------------

Expected:
%(expected)r

Got:
%(result)r
""" % params
    default_msg = """
Expected:
%(expected)s

Got:
%(result)s
""" % params
    if (repr(result) != str(result)) or (repr(expected) != str(expected)):
        default_msg += aka
    assert result == expected, msg or default_msg


def eq_contents(path, text):
    with open(path) as fd:
        eq_(text, fd.read())


def support(path):
    return os.path.join(os.path.dirname(__file__), 'support', path)

fabfile = support


@contextmanager
def path_prefix(module):
    i = 0
    sys.path.insert(i, os.path.dirname(module))
    yield
    sys.path.pop(i)


def aborts(func):
    """
    Decorator declaring that the wrapped test is expected to call ``abort()``.

    The whole test body must raise ``SystemExit``; stderr is captured so the
    abort message does not leak into the test output. This replaces nose's
    ``@raises(SystemExit)``, and keeps the same "anywhere in the body" scope
    that the decorator form had.
    """
    inner = mock_streams('stderr')(func)

    @wraps(inner)
    def wrapper(*args, **kwargs):
        with pytest.raises(SystemExit):
            inner(*args, **kwargs)
    return wrapper


def patched_input(fake):
    """
    Patch the builtin input with ``fake``.

    ``mock.patch.object`` works as both a context manager and a decorator, so
    unlike fudge (which had a separate patched_context/with_patched_object
    pair) one helper covers both uses. ``with_patched_input`` is kept as an
    alias so the decorator form still reads as one at the call site.
    """
    if six.PY3 is True:
        return mock.patch.object(sys.modules['builtins'], 'input', fake)
    else:
        return mock.patch.object(sys.modules['__builtin__'], 'raw_input', fake)
with_patched_input = patched_input
