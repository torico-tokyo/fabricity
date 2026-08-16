"""
Fabric's own fabfile.
"""

from __future__ import with_statement

import os
from fabric.api import task, local, lcd


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
        local("pytest -v %s" % args)
        return
    local("pytest -v")
    # A couple of fabric's own modules carry doctests. They sit outside
    # testpaths, so they need their own run -- pointing --doctest-modules at
    # tests/ instead would try to execute the vendored fudge's Python 2
    # doctests. (The old nose command passed --with-doctest but targeted
    # `tests`, which contains no doctests, so this never actually ran.)
    local("pytest -v --doctest-modules fabric")


@task
def upload():
    with lcd(os.path.dirname(__file__)):
        local('python3 setup.py sdist')
        local('twine upload dist/*')
