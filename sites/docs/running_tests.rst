======================
Running Fabric's Tests
======================

Fabric is maintained with 100% passing tests. Where possible, patches should
include tests covering the changes, making things far easier to verify & merge.

Dependencies are managed with `uv`_, which builds an isolated virtualenv in
``.venv`` from ``pyproject.toml`` and ``uv.lock``.

.. _`uv`: https://docs.astral.sh/uv/

.. _first-time-setup:

First-time Setup
================

* Fork the `repository`_ on GitHub
* Clone your new fork (e.g.
  ``git clone git@github.com:<your_username>/fabricity.git``)
* ``cd fabricity``
* ``uv sync``

``uv sync`` installs the project itself in editable mode along with the
``test``, ``docs`` and ``release`` dependency groups, and uses the Python
version named in ``.python-version``.

.. _`repository`: https://github.com/torico-tokyo/fabricity

.. _running-tests:

Running Tests
=============

Running the tests is just::

    uv run pytest

You should **always** run tests on ``master`` (or the release branch you're
working with) to ensure they're passing before working on your own
changes/tests.

Alternatively::

    uv run fab test

which is the same thing with ``-v`` added, followed by a second pass over
``fabric`` itself to pick up the handful of doctests living outside
``testpaths``.

To run the integration suite (which needs passwordless SSH to the host you
name) use::

    uv run fab -H localhost test:integration

``fab test`` runs pytest *inside* the ``fab`` process rather than shelling out,
because ``-H`` sets the target host in that process only and the integration
tests connect using it directly.

.. note::
    Output capturing is turned off (``--capture=no`` in ``pyproject.toml``). The
    suite replaces ``sys.stdout``/``sys.stderr`` itself and runs a real SSH
    server on localhost, neither of which survives pytest's capturing.

Mocking is done with the standard library's :mod:`unittest.mock`, so there is
no third-party mocking library to install.
