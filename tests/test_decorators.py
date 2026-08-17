import random
import sys

import pytest

from unittest import mock

from fabric import decorators, tasks
from fabric.state import env
import fabric # for patching fabric.state.xxx
from fabric.tasks import _parallel_tasks, requires_parallel, execute
from fabric.context_managers import lcd, settings, hide

from mock_streams import mock_streams
from utils import eq_


#
# Support
#

def fake_function(*args, **kwargs):
    """
    Returns a ``Mock`` exhibiting function-like attributes.

    Passes in all args/kwargs to the ``Mock`` constructor.
    """
    # Must define __name__ to be compatible with function wrapping mechanisms
    # like @wraps().
    return mock.Mock(*args, __name__='fake', **kwargs)



#
# @task
#

def test_task_returns_an_instance_of_wrappedfunctask_object():
    def foo():
        pass
    task = decorators.task(foo)
    assert isinstance(task, tasks.WrappedCallableTask)


def test_task_will_invoke_provided_class():
    def foo(): pass
    task_class = mock.Mock()

    # NOTE: passing task_class makes task() "invoked" (see decorators.task),
    # so it returns a wrapper that has to be applied to get the class built.
    decorators.task(task_class=task_class)(foo)

    task_class.assert_called_once_with(foo)


def test_task_passes_args_to_the_task_class():
    random_vars = ("some text", random.randint(100, 200))
    def foo(): pass

    task_class = mock.Mock()

    decorators.task(*random_vars, task_class=task_class)(foo)

    task_class.assert_called_once_with(foo, *random_vars)


def test_passes_kwargs_to_the_task_class():
    random_vars = {
        "msg": "some text",
        "number": random.randint(100, 200),
    }
    def foo(): pass

    task_class = mock.Mock()

    decorators.task(task_class=task_class, **random_vars)(foo)

    task_class.assert_called_once_with(foo, **random_vars)


def test_integration_tests_for_invoked_decorator_with_no_args():
    r = random.randint(100, 200)
    @decorators.task()
    def foo():
        return r

    eq_(r, foo())


def test_integration_tests_for_decorator():
    r = random.randint(100, 200)
    @decorators.task(task_class=tasks.WrappedCallableTask)
    def foo():
        return r

    eq_(r, foo())


def test_original_non_invoked_style_task():
    r = random.randint(100, 200)
    @decorators.task
    def foo():
        return r

    eq_(r, foo())



#
# @runs_once
#

def test_runs_once_runs_only_once():
    """
    @runs_once prevents decorated func from running >1 time
    """
    func = fake_function()
    task = decorators.runs_once(func)
    for i in range(2):
        task()
    eq_(1, func.call_count)


def test_runs_once_returns_same_value_each_run():
    """
    @runs_once memoizes return value of decorated func
    """
    return_value = "foo"
    task = decorators.runs_once(fake_function(return_value=return_value))
    for i in range(2):
        eq_(task(), return_value)


@decorators.runs_once
def single_run():
    pass

def test_runs_once():
    assert not hasattr(single_run, 'return_value')
    single_run()
    assert hasattr(single_run, 'return_value')
    assert single_run() is None



#
# @serial / @parallel
#


@decorators.serial
def serial():
    pass

@decorators.serial
@decorators.parallel
def serial2():
    pass

@decorators.parallel
@decorators.serial
def serial3():
    pass

@decorators.parallel
def parallel():
    pass

@decorators.parallel(pool_size=20)
def parallel2():
    pass

fake_tasks = {
    'serial': serial,
    'serial2': serial2,
    'serial3': serial3,
    'parallel': parallel,
    'parallel2': parallel2,
}


@pytest.mark.parametrize('task_names, expected', [
    pytest.param(['serial'], False,
                 id="One @serial-decorated task == no parallelism"),
    pytest.param(['parallel'], True,
                 id="One @parallel-decorated task == parallelism"),
    pytest.param(['parallel', 'serial'], True,
                 id="One @parallel- and one @serial-decorated task"
                    " == paralellism"),
    pytest.param(['serial2', 'serial3'], True,
                 id="Tasks decorated with both @serial and @parallel"
                    " count as @parallel"),
])
def test_parallel_tasks(task_names, expected):
    commands_to_run = map(lambda x: [x], task_names)
    with mock.patch.object(fabric.state, 'commands', fake_tasks):
        eq_(_parallel_tasks(commands_to_run), expected)

def test_parallel_wins_vs_serial():
    """
    @parallel takes precedence over @serial when both are used on one task
    """
    assert requires_parallel(serial2)
    assert requires_parallel(serial3)

@mock_streams('stdout')
def test_global_parallel_honors_runs_once():
    """
    fab -P (or env.parallel) should honor @runs_once
    """
    @decorators.runs_once
    def mytask():
        print("yolo") # 'Carpe diem' for stupid people!
    with settings(hide('everything'), parallel=True):
        execute(mytask, hosts=['localhost', '127.0.0.1'])
    result = sys.stdout.getvalue()
    eq_(result, "yolo\n")
    assert result != "yolo\nyolo\n"


#
# @roles
#

@decorators.roles('test')
def use_roles():
    pass

def test_roles():
    assert hasattr(use_roles, 'roles')
    assert use_roles.roles == ['test']



#
# @hosts
#

@decorators.hosts('test')
def use_hosts():
    pass

def test_hosts():
    assert hasattr(use_hosts, 'hosts')
    assert use_hosts.hosts == ['test']



#
# @with_settings
#

def test_with_settings_passes_env_vars_into_decorated_function():
    env.value = True
    random_return = random.randint(1000, 2000)
    def some_task():
        return env.value
    decorated_task = decorators.with_settings(value=random_return)(some_task)
    assert some_task(), "sanity check"
    eq_(random_return, decorated_task())

def test_with_settings_with_other_context_managers():
    """
    with_settings() should take other context managers, and use them with other
    overrided key/value pairs.
    """
    env.testval1 = "outer 1"
    prev_lcwd = env.lcwd

    def some_task():
        eq_(env.testval1, "inner 1")
        assert env.lcwd.endswith("here") # Should be the side-effect of adding cd to settings

    decorated_task = decorators.with_settings(
        lcd("here"),
        testval1="inner 1"
    )(some_task)
    decorated_task()

    assert env.testval1, "outer 1"
    eq_(env.lcwd, prev_lcwd)
