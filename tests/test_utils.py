from __future__ import with_statement

import shlex
import sys
from unittest import TestCase

from fudge import Fake, clear_expectations, patched_context, with_fakes
# NOTE: with_patched_object() works on plain modules/classes but NOT on
# fabric's `output` dict: fudge decides whether an attribute is "local" by
# looking in obj.__dict__, and _AttributeDict keeps its attributes as dict
# *keys*. It therefore treats every flag as newly added and undoes the patch
# with delattr(), which both raises (there is no _AttributeDict.__delattr__)
# and would drop the flag's original value. Use fabric's own show()/hide()
# for output flags instead.
from fudge.patcher import with_patched_object

import pytest

from fabric.state import output
from fabric.utils import warn, indent, abort, puts, fastprint, error
from fabric import utils  # For patching
from fabric.api import local, quiet
from fabric.context_managers import settings, hide, show
from fabric.decorators import with_settings
from fabric.colors import magenta, red
from mock_streams import mock_streams
from utils import aborts, eq_, FabricTest, assert_contains, assert_not_contains


@mock_streams('stderr')
@with_settings(show('warnings'))
def test_warn():
    """
    warn() should print 'Warning' plus given text
    """
    warn("Test")
    eq_("\nWarning: Test\n\n", sys.stderr.getvalue())


@pytest.mark.parametrize('input_, output_', [
    pytest.param('Test', '    Test',
                 id="Sanity check: 1 line string"),
    pytest.param(["Test", "Test"], '    Test\n    Test',
                 id="List of strings turns in to strings joined by \\n"),
])
def test_indent(input_, output_):
    eq_(indent(input_), output_)


@pytest.mark.parametrize('input_, output_', [
    pytest.param('Test', '    Test',
                 id="Sanity check: 1 line string"),
    pytest.param(["Test", "Test"], '    Test\n    Test',
                 id="Check list of strings"),
    pytest.param(["        Test", "        Test"], '    Test\n    Test',
                 id="Check list of over-indented strings"),
])
def test_indent_with_strip(input_, output_):
    eq_(indent(input_, strip=True), output_)


@aborts
def test_abort():
    """
    abort() should raise SystemExit
    """
    abort("Test")

class TestException(Exception):
    pass

def test_abort_with_exception():
    """
    abort() should raise a provided exception
    """
    with pytest.raises(TestException):
        with settings(abort_exception=TestException):
            abort("Test")

@mock_streams('stderr')
@with_settings(show('aborts'))
def test_abort_message():
    """
    abort() should print 'Fatal error' plus exception value
    """
    try:
        abort("Test")
    except SystemExit:
        pass
    result = sys.stderr.getvalue()
    eq_("\nFatal error: Test\n\nAborting.\n", result)

def test_abort_message_only_printed_once():
    """
    abort()'s SystemExit should not cause a reprint of the error message
    """
    # No good way to test the implicit stderr print which sys.exit/SystemExit
    # perform when they are allowed to bubble all the way to the top. So, we
    # invoke a subprocess and look at its stderr instead.
    with quiet():
        # sys.executable rather than "python": local() shells out via /bin/sh,
        # which has no notion of an activated virtualenv, so a bare "python"
        # resolves to whatever is on PATH (often nothing at all). Quoted
        # because the interpreter may live under a path containing spaces.
        result = local(
            "%s -m fabric.__main__ -f tests/support/aborts.py kaboom"
            % shlex.quote(sys.executable),
            capture=True)
    # When error in #1318 is present, this has an extra "It burns!" at end of
    # stderr string.
    eq_(result.stderr, "Fatal error: It burns!\n\nAborting.")

@mock_streams('stderr')
@with_settings(show('aborts'))
def test_abort_exception_contains_separate_message_and_code():
    """
    abort()'s SystemExit contains distinct .code/.message attributes.
    """
    # Re #1318 / #1213
    try:
        abort("Test")
    except SystemExit as e:
        eq_(e.message, "Test")
        eq_(e.code, 1)

@mock_streams('stdout')
def test_puts_with_user_output_on():
    """
    puts() should print input to sys.stdout if "user" output level is on
    """
    s = "string!"
    output.user = True
    puts(s, show_prefix=False)
    eq_(sys.stdout.getvalue(), s + "\n")

@mock_streams('stdout')
def test_puts_with_unicode_output():
    """
    puts() should print unicode input
    """
    s = u"string!"
    output.user = True
    puts(s, show_prefix=False)
    eq_(sys.stdout.getvalue(), s + "\n")


@mock_streams('stdout')
def test_puts_with_encoding_type_none_output():
    """
    puts() should print unicode output without a stream encoding
    """
    s = u"string!"
    output.user = True
    #sys.stdout.encoding = None
    puts(s, show_prefix=False)
    eq_(sys.stdout.getvalue(), s + "\n")

@mock_streams('stdout')
def test_puts_with_user_output_off():
    """
    puts() shouldn't print input to sys.stdout if "user" output level is off
    """
    with settings(hide('user')):
        puts("You aren't reading this.")
    eq_(sys.stdout.getvalue(), "")


@mock_streams('stdout')
def test_puts_with_prefix():
    """
    puts() should prefix output with env.host_string if non-empty
    """
    s = "my output"
    h = "localhost"
    with settings(host_string=h):
        puts(s)
    eq_(sys.stdout.getvalue(), "[%s] %s" % (h, s + "\n"))


@mock_streams('stdout')
def test_puts_without_prefix():
    """
    puts() shouldn't prefix output with env.host_string if show_prefix is False
    """
    s = "my output"
    puts(s, show_prefix=False)
    eq_(sys.stdout.getvalue(), "%s" % (s + "\n"))

@with_fakes
def test_fastprint_calls_puts():
    """
    fastprint() is just an alias to puts()
    """
    # TestErrorHandling's decorators build their Fake(expect_call=True) objects
    # when this module is imported, and those land in fudge's global (process
    # wide) expectation registry. @with_fakes verifies *every* registered
    # expectation, so without this the assertion below fails complaining about
    # someone else's fake. FabricTest.setup_method does the same clearing for
    # class-based tests.
    clear_expectations()
    text = "Some output"
    fake_puts = Fake('puts', expect_call=True).with_args(
        text=text, show_prefix=False, end="", flush=True
    )
    with patched_context(utils, 'puts', fake_puts):
        fastprint(text)


class TestErrorHandling(FabricTest):
    dummy_string = 'test1234!'

    @with_patched_object(utils, 'warn', Fake('warn', callable=True,
        expect_call=True))
    def test_error_warns_if_warn_only_True_and_func_None(self):
        """
        warn_only=True, error(func=None) => calls warn()
        """
        with settings(warn_only=True):
            error('foo')

    @with_patched_object(utils, 'abort', Fake('abort', callable=True,
        expect_call=True))
    def test_error_aborts_if_warn_only_False_and_func_None(self):
        """
        warn_only=False, error(func=None) => calls abort()
        """
        with settings(warn_only=False):
            error('foo')

    def test_error_calls_given_func_if_func_not_None(self):
        """
        error(func=callable) => calls callable()
        """
        error('foo', func=Fake(callable=True, expect_call=True))

    @mock_streams('stdout')
    @with_patched_object(utils, 'abort', Fake('abort', callable=True,
        expect_call=True).calls(lambda x: sys.stdout.write(x + "\n")))
    def test_error_includes_stdout_if_given_and_hidden(self):
        """
        error() correctly prints stdout if it was previously hidden
        """
        # Mostly to catch regression bug(s)
        stdout = "this is my stdout"
        with hide('stdout'):
            error("error message", func=utils.abort, stdout=stdout)
        assert_contains(stdout, sys.stdout.getvalue())

    @mock_streams('stdout')
    @with_patched_object(utils, 'abort', Fake('abort', callable=True,
        expect_call=True).calls(lambda x: sys.stdout.write(x + "\n")))
    @with_settings(show('exceptions'))
    @with_patched_object(utils, 'format_exc', Fake('format_exc', callable=True,
        expect_call=True).returns(dummy_string))
    def test_includes_traceback_if_exceptions_logging_is_on(self):
        """
        error() includes traceback in message if exceptions logging is on
        """
        error("error message", func=utils.abort, stdout=error)
        assert_contains(self.dummy_string, sys.stdout.getvalue())

    @mock_streams('stdout')
    @with_patched_object(utils, 'abort', Fake('abort', callable=True,
        expect_call=True).calls(lambda x: sys.stdout.write(x + "\n")))
    @with_settings(show('debug'))
    @with_patched_object(utils, 'format_exc', Fake('format_exc', callable=True,
        expect_call=True).returns(dummy_string))
    def test_includes_traceback_if_debug_logging_is_on(self):
        """
        error() includes traceback in message if debug logging is on (backwardis compatibility)
        """
        error("error message", func=utils.abort, stdout=error)
        assert_contains(self.dummy_string, sys.stdout.getvalue())

    @mock_streams('stdout')
    @with_patched_object(utils, 'abort', Fake('abort', callable=True,
        expect_call=True).calls(lambda x: sys.stdout.write(x + "\n")))
    @with_settings(show('exceptions'))
    @with_patched_object(utils, 'format_exc', Fake('format_exc', callable=True,
        expect_call=True).returns(None))
    def test_doesnt_print_None_when_no_traceback_present(self):
        """
        error() doesn't include None in message if there is no traceback
        """
        error("error message", func=utils.abort, stdout=error)
        assert_not_contains('None', sys.stdout.getvalue())

    @mock_streams('stderr')
    @with_patched_object(utils, 'abort', Fake('abort', callable=True,
        expect_call=True).calls(lambda x: sys.stderr.write(x + "\n")))
    def test_error_includes_stderr_if_given_and_hidden(self):
        """
        error() correctly prints stderr if it was previously hidden
        """
        # Mostly to catch regression bug(s)
        stderr = "this is my stderr"
        with hide('stderr'):
            error("error message", func=utils.abort, stderr=stderr)
        assert_contains(stderr, sys.stderr.getvalue())

    @mock_streams('stderr')
    def test_warnings_print_magenta_if_colorize_on(self):
        with settings(colorize_errors=True):
            error("oh god", func=utils.warn, stderr="oops")
        # can't use assert_contains as ANSI codes contain regex specialchars
        eq_(magenta("\nWarning: oh god\n\n"), sys.stderr.getvalue())

    @mock_streams('stderr')
    def test_errors_print_red_if_colorize_on(self):
        # NOTE: abort() raises SystemExit out of the error() call, so the
        # stderr assertion below is unreachable. That was already true under
        # nose's @raises(SystemExit) decorator, which wrapped the whole body;
        # the pytest.raises block keeps the same scope rather than silently
        # enabling an assertion that has never actually run.
        with pytest.raises(SystemExit):
            with settings(colorize_errors=True):
                error("oh god", func=utils.abort, stderr="oops")
            # can't use assert_contains as ANSI codes contain regex
            # specialchars
            eq_(red("\\Error: oh god\n\n"), sys.stderr.getvalue())
