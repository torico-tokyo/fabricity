"""
Fabric's own fabfile.
"""

from __future__ import with_statement

import os
import shlex
from fabric.api import task, abort, local, lcd


def _pytest(args):
    """
    Run pytest inside *this* process and abort if anything failed.

    Deliberately not run via ``local()``: ``fab -H localhost test:integration``
    sets ``env.host_string`` in this process only, and the integration suite
    calls ``run()``/``sudo()`` directly rather than selecting a host itself. A
    subprocess would start with no host set and prompt for one (or abort)
    instead of connecting. The nose runner this replaced ran in-process for
    the same reason.
    """
    import pytest

    code = pytest.main(["-v"] + args)
    if code != 0:
        abort("pytest exited with code %s" % int(code))


@task(default=True)
def test(args=None):
    """
    Run all unit tests.

    Specify string argument ``args`` for additional args to ``pytest``, e.g.
    ``fab test:integration`` to run the integration suite instead.
    """
    # Output capturing is disabled in setup.cfg (the suite replaces
    # sys.stdout/sys.stderr itself and runs a real local SSH server), so no
    # -s is needed here.
    if args:
        # shlex, not str.split: running in-process means no shell is involved
        # any more, so quoting like ``fab test:'-k "foo or bar"'`` has to be
        # honoured here instead.
        _pytest(shlex.split(args))
        return
    _pytest([])
    # A couple of fabric's own modules carry doctests. They sit outside
    # testpaths, so they need their own run -- pointing --doctest-modules at
    # tests/ instead would try to execute the vendored fudge's Python 2
    # doctests. (The old nose command passed --with-doctest but targeted
    # `tests`, which contains no doctests, so this never actually ran.)
    _pytest(["--doctest-modules", "fabric"])


@task
def upload():
    with lcd(os.path.dirname(__file__)):
        local('python3 setup.py sdist')
        local('twine upload dist/*')
