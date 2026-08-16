from __future__ import with_statement

import sys

import pytest
from fudge import (Fake, patch_object, with_patched_object, patched_context,
                   with_fakes)

from fabric.context_managers import settings, hide, show
from fabric.network import (HostConnectionCache, join_host_strings, normalize,
                            denormalize, key_filenames, key_from_env, ssh,
                            NetworkError, connect)
import fabric.network  # So I can call patch_object correctly. Sigh.
from fabric.state import env, output, _get_system_username
from fabric.operations import run, sudo, prompt
from fabric.tasks import execute
from fabric.api import parallel
from fabric import utils # for patching

from mock_streams import mock_streams
from server import (server, RESPONSES, PASSWORDS, CLIENT_PRIVKEY, USER,
                    CLIENT_PRIVKEY_PASSPHRASE)
from utils import (FabricTest, aborts, assert_contains, eq_, password_response,
                   patched_input, support)


# normalize() falls back to the current system user, so expected host strings
# are built from it. Resolved once at import time because @parametrize
# arguments are evaluated during collection, not inside the test.
SYSTEM_USERNAME = _get_system_username()


#
# Subroutines, e.g. host string normalization
#


# NOTE: these normalization checks are deliberately module-level functions
# rather than TestNetwork methods. They assert against the *default* env (the
# system username, port 22), whereas FabricTest.setup_method points env at the
# local test server (user 'username', port 2200). Under nose they ran outside
# that setup because they were generator-based; keeping them out of the class
# preserves what they actually assert.
@pytest.mark.parametrize('input, output_', [
    pytest.param('localhost', 'localhost',
                 id="Sanity check: equal strings remain equal"),
    pytest.param('localhost', SYSTEM_USERNAME + '@localhost',
                 id="Empty username is same as get_system_username"),
    pytest.param('localhost', 'localhost:22',
                 id="Empty port is same as port 22"),
    pytest.param('localhost', SYSTEM_USERNAME + '@localhost:22',
                 id="Both username and port tested at once, for kicks"),
])
def test_host_string_normalization(input, output_):
    eq_(normalize(input), normalize(output_))


@pytest.mark.parametrize('input, output_', [
    pytest.param('2001:DB8:0:0:0:0:0:1',
                 (SYSTEM_USERNAME, '2001:DB8:0:0:0:0:0:1', '22'),
                 id="Full IPv6 address"),
    pytest.param('2001:DB8::1', (SYSTEM_USERNAME, '2001:DB8::1', '22'),
                 id="IPv6 address in short form"),
    pytest.param('::1', (SYSTEM_USERNAME, '::1', '22'),
                 id="IPv6 localhost"),
    pytest.param('[2001:DB8::1]:1222',
                 (SYSTEM_USERNAME, '2001:DB8::1', '1222'),
                 id="Square brackets are required to separate"
                    " non-standard port from IPv6 address"),
    pytest.param('user@2001:DB8::1', ('user', '2001:DB8::1', '22'),
                 id="Username and IPv6 address"),
    pytest.param('user@[2001:DB8::1]:1222', ('user', '2001:DB8::1', '1222'),
                 id="Username and IPv6 address with non-standard port"),
])
def test_normalization_for_ipv6(input, output_):
    """
    normalize() will accept IPv6 notation and can separate host and port
    """
    eq_(normalize(input), output_)


@pytest.mark.parametrize('input', [
    pytest.param('', id="empty string"),
    pytest.param(None, id="None"),
])
def test_normalization_of_empty_input(input):
    """
    normalize() returns empty strings for empty input
    """
    eq_(normalize(input), ('', '', ''))


@pytest.mark.parametrize('string1, string2', [
    pytest.param('localhost', 'localhost',
                 id="Sanity check: equal strings remain equal"),
    pytest.param('localhost:22', SYSTEM_USERNAME + '@localhost:22',
                 id="Empty username is same as get_system_username"),
    pytest.param('user@localhost', 'user@localhost:22',
                 id="Empty port is same as port 22"),
    pytest.param('localhost', SYSTEM_USERNAME + '@localhost:22',
                 id="Both username and port"),
    pytest.param('2001:DB8::1', SYSTEM_USERNAME + '@[2001:DB8::1]:22',
                 id="IPv6 address"),
])
def test_host_string_denormalization(string1, string2):
    eq_(denormalize(string1), denormalize(string2))


class TestNetwork(FabricTest):
    def test_normalization_without_port(self):
        """
        normalize() and join_host_strings() omit port if omit_port given
        """
        eq_(
            join_host_strings(*normalize('user@localhost', omit_port=True)),
            'user@localhost'
        )

    def test_ipv6_host_strings_join(self):
        """
        join_host_strings() should use square brackets only for IPv6 and if port is given
        """
        eq_(
            join_host_strings('user', '2001:DB8::1'),
            'user@2001:DB8::1'
        )
        eq_(
            join_host_strings('user', '2001:DB8::1', '1222'),
            'user@[2001:DB8::1]:1222'
        )
        eq_(
            join_host_strings('user', '192.168.0.0', '1222'),
            'user@192.168.0.0:1222'
        )

    def test_nonword_character_in_username(self):
        """
        normalize() will accept non-word characters in the username part
        """
        eq_(
            normalize('user-with-hyphens@someserver.org')[0],
            'user-with-hyphens'
        )

    def test_at_symbol_in_username(self):
        """
        normalize() should allow '@' in usernames (i.e. last '@' is split char)
        """
        parts = normalize('user@example.com@www.example.com')
        eq_(parts[0], 'user@example.com')
        eq_(parts[1], 'www.example.com')

    #
    # Connection caching
    #
    @staticmethod
    @with_fakes
    def check_connection_calls(host_strings, num_calls):
        # Clear Fudge call stack
        # Patch connect() with Fake obj set to expect num_calls calls
        patched_connect = patch_object('fabric.network', 'connect',
            Fake('connect', expect_call=True).times_called(num_calls)
        )
        try:
            # Make new cache object
            cache = HostConnectionCache()
            # Connect to all connection strings
            for host_string in host_strings:
                # Obtain connection from cache, potentially calling connect()
                cache[host_string]
        finally:
            # Restore connect()
            patched_connect.restore()

    @pytest.mark.parametrize('host_strings, num_calls', [
        pytest.param(('localhost', 'other-system'), 2,
                     id="Two different host names, two connections"),
        pytest.param(('localhost', 'localhost'), 1,
                     id="Same host twice, one connection"),
        pytest.param(('localhost:22', 'localhost:222'), 2,
                     id="Same host twice, different ports, two connections"),
        pytest.param(('user1@localhost', 'user2@localhost'), 2,
                     id="Same host twice, different users, two connections"),
    ])
    def test_connection_caching(self, host_strings, num_calls):
        TestNetwork.check_connection_calls(host_strings, num_calls)

    def test_connection_cache_deletion(self):
        """
        HostConnectionCache should delete correctly w/ non-full keys
        """
        hcc = HostConnectionCache()
        fake = Fake('connect', callable=True)
        with patched_context('fabric.network', 'connect', fake):
            for host_string in ('hostname', 'user@hostname',
                'user@hostname:222'):
                # Prime
                hcc[host_string]
                # Test
                assert host_string in hcc
                # Delete
                del hcc[host_string]
                # Test
                assert host_string not in hcc


    #
    # Connection loop flow
    #
    @server()
    def test_saved_authentication_returns_client_object(self):
        cache = HostConnectionCache()
        assert isinstance(cache[env.host_string], ssh.SSHClient)

    @server()
    @with_fakes
    def test_prompts_for_password_without_good_authentication(self):
        env.password = None
        with password_response(PASSWORDS[env.user], times_called=1):
            cache = HostConnectionCache()
            cache[env.host_string]


    @aborts
    def test_aborts_on_prompt_with_abort_on_prompt(self):
        """
        abort_on_prompt=True should abort when prompt() is used
        """
        env.abort_on_prompts = True
        prompt("This will abort")


    @server()
    @aborts
    def test_aborts_on_password_prompt_with_abort_on_prompt(self):
        """
        abort_on_prompt=True should abort when password prompts occur
        """
        env.password = None
        env.abort_on_prompts = True
        with password_response(PASSWORDS[env.user], times_called=1):
            cache = HostConnectionCache()
            cache[env.host_string]

    @with_fakes
    def test_connect_does_not_prompt_password_when_ssh_raises_channel_exception(self):
        def raise_channel_exception_once(*args, **kwargs):
            if raise_channel_exception_once.should_raise_channel_exception:
                raise_channel_exception_once.should_raise_channel_exception = False
                raise ssh.ChannelException(2, 'Connect failed')
        raise_channel_exception_once.should_raise_channel_exception = True

        def generate_fake_client():
            # NOTE: no expect_call=True here. This fake stands in for the
            # SSHClient *instance*, which connect() only ever calls methods on
            # -- it never invokes the object itself, so an expect_call on it
            # can never be satisfied. What this test actually asserts is the
            # times_called(0) on prompt_for_password below.
            fake_client = Fake('SSHClient', allows_any_call=True)
            fake_client.provides('connect').calls(raise_channel_exception_once)
            return fake_client

        fake_ssh = Fake('ssh', allows_any_call=True)
        fake_ssh.provides('SSHClient').calls(generate_fake_client)
        # We need the real exceptions here to preserve the inheritence
        # structure -- and every exception class connect() names in an `except`
        # clause has to be a real one, or evaluating that clause raises
        # "TypeError: catching classes that do not inherit from BaseException".
        fake_ssh.SSHException = ssh.SSHException
        fake_ssh.ChannelException = ssh.ChannelException
        fake_ssh.BadHostKeyException = ssh.BadHostKeyException
        fake_ssh.AuthenticationException = ssh.AuthenticationException
        fake_ssh.PasswordRequiredException = ssh.PasswordRequiredException
        patched_connect = patch_object('fabric.network', 'ssh', fake_ssh)
        patched_password = patch_object('fabric.network', 'prompt_for_password', Fake('prompt_for_password', callable = True).times_called(0))
        try:
            with pytest.raises(NetworkError):
                connect('user', 'localhost', 22, HostConnectionCache())
        finally:
            # Restore ssh
            patched_connect.restore()
            patched_password.restore()


    @mock_streams('stdout')
    @server()
    def test_does_not_abort_with_password_and_host_with_abort_on_prompt(self):
        """
        abort_on_prompt=True should not abort if no prompts are needed
        """
        env.abort_on_prompts = True
        env.password = PASSWORDS[env.user]
        # env.host_string is automatically filled in when using server()
        run("ls /simple")


    @mock_streams('stdout')
    @server()
    def test_trailing_newline_line_drop(self):
        """
        Trailing newlines shouldn't cause last line to be dropped.
        """
        # Multiline output with trailing newline
        cmd = "ls /"
        output_string = RESPONSES[cmd]
        # TODO: fix below lines, duplicates inner workings of tested code
        prefix = "[%s] out: " % env.host_string
        expected = prefix + ('\n' + prefix).join(output_string.split('\n'))
        # Create, tie off thread
        with settings(show('everything'), hide('running')):
            result = run(cmd)
            # Test equivalence of expected, received output
            eq_(expected, sys.stdout.getvalue())
            # Also test that the captured value matches, too.
            eq_(output_string, result)

    @server()
    def test_sudo_prompt_kills_capturing(self):
        """
        Sudo prompts shouldn't screw up output capturing
        """
        cmd = "ls /simple"
        with hide('everything'):
            eq_(sudo(cmd), RESPONSES[cmd])

    @server()
    def test_password_memory_on_user_switch(self):
        """
        Switching users mid-session should not screw up password memory
        """
        def _to_user(user):
            return join_host_strings(user, env.host, env.port)

        user1 = 'root'
        user2 = USER
        with settings(hide('everything'), password=None):
            # Connect as user1 (thus populating both the fallback and
            # user-specific caches)
            with settings(
                password_response(PASSWORDS[user1]),
                host_string=_to_user(user1)
            ):
                run("ls /simple")
            # Connect as user2: * First cxn attempt will use fallback cache,
            # which contains user1's password, and thus fail * Second cxn
            # attempt will prompt user, and succeed due to mocked p4p * but
            # will NOT overwrite fallback cache
            with settings(
                password_response(PASSWORDS[user2]),
                host_string=_to_user(user2)
            ):
                # Just to trigger connection
                run("ls /simple")
            # * Sudo call should use cached user2 password, NOT fallback cache,
            # and thus succeed. (I.e. p_f_p should NOT be called here.)
            with settings(
                password_response('whatever', times_called=0),
                host_string=_to_user(user2)
            ):
                sudo("ls /simple")

    @mock_streams('stderr')
    @server()
    def test_password_prompt_displays_host_string(self):
        """
        Password prompt lines should include the user/host in question
        """
        env.password = None
        env.no_agent = env.no_keys = True
        with show('everything'), password_response(PASSWORDS[env.user], silent=False):
            run("ls /simple")
        regex = r'^\[%s\] Login password for \'%s\': ' % (env.host_string, env.user)
        assert_contains(regex, sys.stderr.getvalue())

    @mock_streams('stderr')
    @server(pubkeys=True)
    def test_passphrase_prompt_displays_host_string(self):
        """
        Passphrase prompt lines should include the user/host in question
        """
        env.password = None
        env.no_agent = env.no_keys = True
        env.key_filename = CLIENT_PRIVKEY
        with hide('everything'), password_response(CLIENT_PRIVKEY_PASSPHRASE, silent=False):
            run("ls /simple")
        regex = r'^\[%s\] Login password for \'%s\': ' % (env.host_string, env.user)
        assert_contains(regex, sys.stderr.getvalue())

    def test_sudo_prompt_display_passthrough(self):
        """
        Sudo prompt should display (via passthrough) when stdout/stderr shown
        """
        TestNetwork._prompt_display(True)

    def test_sudo_prompt_display_directly(self):
        """
        Sudo prompt should display (manually) when stdout/stderr hidden
        """
        TestNetwork._prompt_display(False)

    @staticmethod
    @mock_streams('both')
    @server(pubkeys=True, responses={'oneliner': 'result'})
    def _prompt_display(display_output):
        env.password = None
        env.no_agent = env.no_keys = True
        env.key_filename = CLIENT_PRIVKEY
        output.output = display_output
        with password_response(
            (CLIENT_PRIVKEY_PASSPHRASE, PASSWORDS[env.user]),
            silent=False
        ):
            sudo('oneliner')
        if display_output:
            expected = """
[%(prefix)s] sudo: oneliner
[%(prefix)s] Login password for '%(user)s': \n[%(prefix)s] out: sudo password:
[%(prefix)s] out: Sorry, try again.
[%(prefix)s] out: sudo password: \n[%(prefix)s] out: result
""" % {'prefix': env.host_string, 'user': env.user}
        else:
            # Note lack of first sudo prompt (as it's autoresponded to) and of
            # course the actual result output.
            expected = """
[%(prefix)s] sudo: oneliner
[%(prefix)s] Login password for '%(user)s': \n[%(prefix)s] out: Sorry, try again.
[%(prefix)s] out: sudo password: """ % {
    'prefix': env.host_string,
    'user': env.user
}
        eq_(expected[1:], sys.stdall.getvalue())

    @mock_streams('both')
    @server(
        pubkeys=True,
        responses={'oneliner': 'result', 'twoliner': 'result1\nresult2'}
    )
    def test_consecutive_sudos_should_not_have_blank_line(self):
        """
        Consecutive sudo() calls should not incur a blank line in-between
        """
        env.password = None
        env.no_agent = env.no_keys = True
        env.key_filename = CLIENT_PRIVKEY
        with password_response(
            (CLIENT_PRIVKEY_PASSPHRASE, PASSWORDS[USER]),
            silent=False
        ):
            sudo('oneliner')
            sudo('twoliner')
        expected = """
[%(prefix)s] sudo: oneliner
[%(prefix)s] Login password for '%(user)s': \n[%(prefix)s] out: sudo password:
[%(prefix)s] out: Sorry, try again.
[%(prefix)s] out: sudo password: \n[%(prefix)s] out: result
[%(prefix)s] sudo: twoliner
[%(prefix)s] out: sudo password:
[%(prefix)s] out: result1
[%(prefix)s] out: result2
""" % {'prefix': env.host_string, 'user': env.user}
        eq_(sys.stdall.getvalue(), expected[1:])

    @mock_streams('both')
    @server(pubkeys=True, responses={'silent': '', 'normal': 'foo'})
    def test_silent_commands_should_not_have_blank_line(self):
        """
        Silent commands should not generate an extra trailing blank line

        After the move to interactive I/O, it was noticed that while run/sudo
        commands which had non-empty stdout worked normally (consecutive such
        commands were totally adjacent), those with no stdout (i.e. silent
        commands like ``test`` or ``mkdir``) resulted in spurious blank lines
        after the "run:" line. This looks quite ugly in real world scripts.
        """
        env.password = None
        env.no_agent = env.no_keys = True
        env.key_filename = CLIENT_PRIVKEY
        with password_response(CLIENT_PRIVKEY_PASSPHRASE, silent=False):
            run('normal')
            run('silent')
            run('normal')
            with hide('everything'):
                run('normal')
                run('silent')
        expected = """
[%(prefix)s] run: normal
[%(prefix)s] Login password for '%(user)s': \n[%(prefix)s] out: foo
[%(prefix)s] run: silent
[%(prefix)s] run: normal
[%(prefix)s] out: foo
""" % {'prefix': env.host_string, 'user': env.user}
        eq_(expected[1:], sys.stdall.getvalue())

    @mock_streams('both')
    @server(
        pubkeys=True,
        responses={'oneliner': 'result', 'twoliner': 'result1\nresult2'}
    )
    def test_io_should_print_prefix_if_ouput_prefix_is_true(self):
        """
        run/sudo should print [host_string] if env.output_prefix == True
        """
        env.password = None
        env.no_agent = env.no_keys = True
        env.key_filename = CLIENT_PRIVKEY
        with password_response(
            (CLIENT_PRIVKEY_PASSPHRASE, PASSWORDS[USER]),
            silent=False
        ):
            run('oneliner')
            run('twoliner')
        expected = """
[%(prefix)s] run: oneliner
[%(prefix)s] Login password for '%(user)s': \n[%(prefix)s] out: result
[%(prefix)s] run: twoliner
[%(prefix)s] out: result1
[%(prefix)s] out: result2
""" % {'prefix': env.host_string, 'user': env.user}
        eq_(expected[1:], sys.stdall.getvalue())

    @mock_streams('both')
    @server(
        pubkeys=True,
        responses={'oneliner': 'result', 'twoliner': 'result1\nresult2'}
    )
    def test_io_should_not_print_prefix_if_ouput_prefix_is_false(self):
        """
        run/sudo shouldn't print [host_string] if env.output_prefix == False
        """
        env.password = None
        env.no_agent = env.no_keys = True
        env.key_filename = CLIENT_PRIVKEY
        with password_response(
            (CLIENT_PRIVKEY_PASSPHRASE, PASSWORDS[USER]),
            silent=False
        ):
            with settings(output_prefix=False):
                run('oneliner')
                run('twoliner')
        expected = """
[%(prefix)s] run: oneliner
[%(prefix)s] Login password for '%(user)s': \nresult
[%(prefix)s] run: twoliner
result1
result2
""" % {'prefix': env.host_string, 'user': env.user}
        eq_(expected[1:], sys.stdall.getvalue())

    @server()
    def test_env_host_set_when_host_prompt_used(self):
        """
        Ensure env.host is set during host prompting
        """
        copied_host_string = str(env.host_string)
        fake = Fake('raw_input', callable=True).returns(copied_host_string)
        env.host_string = None
        env.host = None
        with settings(hide('everything'), patched_input(fake)):
            run("ls /")
        # Ensure it did set host_string back to old value
        eq_(env.host_string, copied_host_string)
        # Ensure env.host is correct
        eq_(env.host, normalize(copied_host_string)[1])


def subtask():
    run("This should never execute")

class TestConnections(FabricTest):
    @aborts
    def test_should_abort_when_cannot_connect(self):
        """
        By default, connecting to a nonexistent server should abort.
        """
        with hide('everything'):
            execute(subtask, hosts=['nope.nonexistent.com'])

    def test_should_warn_when_skip_bad_hosts_is_True(self):
        """
        env.skip_bad_hosts = True => execute() skips current host
        """
        with settings(hide('everything'), skip_bad_hosts=True):
            execute(subtask, hosts=['nope.nonexistent.com'])

    @server()
    def test_host_not_in_known_hosts_exception(self):
        """
        Check reject_unknown_hosts exception
        """
        with settings(
            hide('everything'), password=None, reject_unknown_hosts=True,
            disable_known_hosts=True, abort_on_prompts=True,
        ):
            try:
                run("echo foo")
            except NetworkError as exc:
                exp = "Server '[127.0.0.1]:2200' not found in known_hosts"
                assert str(exc) == exp, "%s != %s" % (exc, exp)
            else:
                raise AssertionError("Host connected without valid "
                                     "fingerprint.")


@parallel
def parallel_subtask():
    run("This should never execute")

class TestParallelConnections(FabricTest):
    @aborts
    def test_should_abort_when_cannot_connect(self):
        """
        By default, connecting to a nonexistent server should abort.
        """
        with hide('everything'):
            execute(parallel_subtask, hosts=['nope.nonexistent.com'])

    def test_should_warn_when_skip_bad_hosts_is_True(self):
        """
        env.skip_bad_hosts = True => execute() skips current host
        """
        with settings(hide('everything'), skip_bad_hosts=True):
            execute(parallel_subtask, hosts=['nope.nonexistent.com'])


class TestSSHConfig(FabricTest):
    def env_setup(self):
        super(TestSSHConfig, self).env_setup()
        env.use_ssh_config = True
        env.ssh_config_path = support("ssh_config")
        # Undo the changes FabricTest makes to env for server support
        env.user = env.local_user
        env.port = env.default_port

    def test_global_user_with_default_env(self):
        """
        Global User should override default env.user
        """
        eq_(normalize("localhost")[0], "satan")

    def test_global_user_with_nondefault_env(self):
        """
        Global User should NOT override nondefault env.user
        """
        with settings(user="foo"):
            eq_(normalize("localhost")[0], "foo")

    def test_specific_user_with_default_env(self):
        """
        Host-specific User should override default env.user
        """
        eq_(normalize("myhost")[0], "neighbor")

    def test_user_vs_host_string_value(self):
        """
        SSH-config derived user should NOT override host-string user value
        """
        eq_(normalize("myuser@localhost")[0], "myuser")
        eq_(normalize("myuser@myhost")[0], "myuser")

    def test_global_port_with_default_env(self):
        """
        Global Port should override default env.port
        """
        eq_(normalize("localhost")[2], "666")

    def test_global_port_with_nondefault_env(self):
        """
        Global Port should NOT override nondefault env.port
        """
        with settings(port="777", use_ssh_config=False):
            eq_(normalize("localhost")[2], "777")

    def test_specific_port_with_default_env(self):
        """
        Host-specific Port should override default env.port
        """
        eq_(normalize("myhost")[2], "664")

    def test_port_vs_host_string_value(self):
        """
        SSH-config derived port should NOT override host-string port value
        """
        eq_(normalize("localhost:123")[2], "123")
        eq_(normalize("myhost:123")[2], "123")

    def test_hostname_alias(self):
        """
        Hostname setting overrides host string's host value
        """
        eq_(normalize("localhost")[1], "localhost")
        eq_(normalize("myalias")[1], "otherhost")

    @with_patched_object(utils, 'warn', Fake('warn', callable=True,
        expect_call=True))
    def test_warns_with_bad_config_file_path(self):
        # use_ssh_config is already set in our env_setup()
        with settings(hide('everything'), ssh_config_path="nope_bad_lol"):
            normalize('foo')

    @server()
    def test_real_connection(self):
        """
        Test-server connection using ssh_config values
        """
        with settings(
            hide('everything'),
            ssh_config_path=support("testserver_ssh_config"),
            host_string='testserver',
        ):
            assert run("ls /simple").succeeded


class TestKeyFilenames(FabricTest):
    def test_empty_everything(self):
        """
        No env.key_filename and no ssh_config = empty list
        """
        with settings(use_ssh_config=False):
            with settings(key_filename=""):
                eq_(key_filenames(), [])
            with settings(key_filename=[]):
                eq_(key_filenames(), [])

    def test_just_env(self):
        """
        Valid env.key_filename and no ssh_config = just env
        """
        with settings(use_ssh_config=False):
            with settings(key_filename="mykey"):
                eq_(key_filenames(), ["mykey"])
            with settings(key_filename=["foo", "bar"]):
                eq_(key_filenames(), ["foo", "bar"])

    def test_just_ssh_config(self):
        """
        No env.key_filename + valid ssh_config = ssh value
        """
        with settings(use_ssh_config=True, ssh_config_path=support("ssh_config")):
            for val in ["", []]:
                with settings(key_filename=val):
                    eq_(key_filenames(), ["foobar.pub"])

    def test_both(self):
        """
        Both env.key_filename + valid ssh_config = both show up w/ env var first
        """
        with settings(use_ssh_config=True, ssh_config_path=support("ssh_config")):
            with settings(key_filename="bizbaz.pub"):
                eq_(key_filenames(), ["bizbaz.pub", "foobar.pub"])
            with settings(key_filename=["bizbaz.pub", "whatever.pub"]):
                expected = ["bizbaz.pub", "whatever.pub", "foobar.pub"]
                eq_(key_filenames(), expected)


def _private_key_text(kind, passphrase=None):
    """
    Generate a fresh private key of ``kind`` as OpenSSH-format PEM text.

    Generated rather than checked in so the suite never carries a real key,
    and so each key type is exercised as paramiko would actually receive it.
    """
    from cryptography.hazmat.primitives import serialization
    from cryptography.hazmat.primitives.asymmetric import ec, ed25519, rsa

    if kind == 'ed25519':
        key = ed25519.Ed25519PrivateKey.generate()
    elif kind == 'ecdsa':
        key = ec.generate_private_key(ec.SECP256R1())
    elif kind == 'rsa':
        key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    else:
        raise ValueError(kind)
    if passphrase is None:
        encryption = serialization.NoEncryption()
    else:
        encryption = serialization.BestAvailableEncryption(
            passphrase.encode('utf-8'))
    return key.private_bytes(
        serialization.Encoding.PEM,
        serialization.PrivateFormat.OpenSSH,
        encryption,
    ).decode('ascii')


class TestKeyFromEnv(FabricTest):
    """
    env.key (a private key passed as text) is turned into a paramiko key.
    """
    @pytest.mark.parametrize('kind, expected', [
        # ed25519/ecdsa are regression cases: the candidate list used to be
        # (RSAKey, DSSKey) only, so these keys could not be loaded at all.
        ('ed25519', 'Ed25519Key'),
        ('ecdsa', 'ECDSAKey'),
        ('rsa', 'RSAKey'),
    ])
    def test_loads_each_supported_key_type(self, kind, expected):
        with settings(key=_private_key_text(kind)):
            pkey = key_from_env()
        assert pkey is not None, "%s key failed to load" % kind
        eq_(pkey.__class__.__name__, expected)

    def test_returns_none_when_env_key_unset(self):
        # FabricTest's env has no 'key' at all; nothing to load.
        assert 'key' not in env
        assert key_from_env() is None

    def test_returns_none_for_garbage(self):
        with settings(key="not a key at all"):
            assert key_from_env() is None

    # All three types are checked because the whole point of the candidate
    # list is that each is parsed by a different class, and paramiko does not
    # word the "encrypted" error identically across them.
    @pytest.mark.parametrize('kind', ['ed25519', 'ecdsa', 'rsa'])
    def test_encrypted_key_raises_so_caller_can_prompt(self, kind):
        """
        connect() catches PasswordRequiredException to re-prompt; swallowing it
        here would silently pass pkey=None instead.
        """
        with settings(key=_private_key_text(kind, passphrase='secret')):
            with pytest.raises(ssh.PasswordRequiredException):
                key_from_env()

    @pytest.mark.parametrize('kind, expected', [
        ('ed25519', 'Ed25519Key'),
        ('ecdsa', 'ECDSAKey'),
        ('rsa', 'RSAKey'),
    ])
    def test_encrypted_key_loads_once_passphrase_is_supplied(self, kind,
                                                             expected):
        with settings(key=_private_key_text(kind, passphrase='secret')):
            pkey = key_from_env('secret')
        assert pkey is not None
        eq_(pkey.__class__.__name__, expected)


class TestDisabledAlgorithms(FabricTest):
    """
    env.disabled_algorithms is handed to paramiko so 3des-cbc is not offered.
    """
    @staticmethod
    def _all_connect_kwargs(seek_gateway=False, **extra_settings):
        """
        Run connect() against a stand-in SSHClient and return the kwargs of
        every connect() call it made, in order.

        With a gateway configured there are two: the gateway itself first,
        then the real target.
        """
        calls = []

        class RecordingClient(object):
            def load_system_host_keys(self, *args, **kwargs):
                pass

            def set_missing_host_key_policy(self, *args, **kwargs):
                pass

            def connect(self, **kwargs):
                calls.append(kwargs)

            def get_transport(self):
                # Only reached on the gateway path, via direct_tcpip().
                return Fake('transport').provides('open_channel').returns(
                    Fake('channel'))

        real = fabric.network.ssh.SSHClient
        fabric.network.ssh.SSHClient = RecordingClient
        try:
            with settings(hide('everything'), use_ssh_config=False,
                          **extra_settings):
                connect('user', 'localhost', 22, HostConnectionCache(),
                        seek_gateway=seek_gateway)
        finally:
            fabric.network.ssh.SSHClient = real
        return calls

    @classmethod
    def _connect_kwargs(cls, **extra_settings):
        return cls._all_connect_kwargs(**extra_settings)[-1]

    def test_3des_is_disabled_by_default(self):
        kwargs = self._connect_kwargs()
        eq_(kwargs['disabled_algorithms'], {'ciphers': ['3des-cbc']})

    def test_can_be_overridden_via_env(self):
        """
        Old gear with nothing better must remain reachable without a patch.
        """
        kwargs = self._connect_kwargs(disabled_algorithms={})
        eq_(kwargs['disabled_algorithms'], {})

    def test_gateway_connection_gets_it_too(self):
        """
        Gateways are reached by connect() calling itself, so the setting has
        to land on both hops. Pinned down so a future rewrite of that path
        cannot quietly leave the gateway offering 3des-cbc.
        """
        calls = self._all_connect_kwargs(seek_gateway=True,
                                         gateway='gw.example.com')
        eq_(len(calls), 2)  # gateway, then target
        for kwargs in calls:
            eq_(kwargs['disabled_algorithms'], {'ciphers': ['3des-cbc']})

    def test_cbc_is_left_enabled(self):
        """
        Dropping aes*-cbc too is a separate decision; make it explicit.
        """
        disabled = self._connect_kwargs()['disabled_algorithms']
        for name in ('aes128-cbc', 'aes192-cbc', 'aes256-cbc'):
            assert name not in disabled['ciphers']

    def test_setting_actually_removes_3des_from_what_paramiko_offers(self):
        """
        End-to-end on the paramiko side: the value we pass really does drop
        3des-cbc from the cipher list a Transport will negotiate with.

        Checked against Transport.preferred_ciphers (the filtered property),
        not _preferred_ciphers (the raw class attribute, which is left
        untouched). Also guards the premise: if paramiko ever stops offering
        3des-cbc by default, this setting becomes dead weight.
        """
        import socket

        ours, theirs = socket.socketpair()
        try:
            disabled = ssh.Transport(
                ours, disabled_algorithms=env.disabled_algorithms)
            default = ssh.Transport(theirs)
            assert '3des-cbc' in default.preferred_ciphers, \
                "paramiko no longer offers 3des-cbc; revisit this setting"
            assert '3des-cbc' not in disabled.preferred_ciphers
            # Nothing else should have been dropped along the way.
            eq_(
                set(default.preferred_ciphers)
                - set(disabled.preferred_ciphers),
                {'3des-cbc'},
            )
        finally:
            ours.close()
            theirs.close()
