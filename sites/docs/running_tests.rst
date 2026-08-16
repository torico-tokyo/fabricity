======================
Running Fabric's Tests
======================

Fabric is maintained with 100% passing tests. Where possible, patches should
include tests covering the changes, making things far easier to verify & merge.

When developing on Fabric, it works best to establish a `virtualenv`_ to install
the dependencies in isolation for running tests.

.. _`virtualenv`: https://virtualenv.pypa.io/en/latest/

.. _first-time-setup:

First-time Setup
================

* Fork the `repository`_ on GitHub
* Clone your new fork (e.g.
  ``git clone git@github.com:<your_username>/fabric.git``)
* ``cd fabric``
* ``virtualenv env``
* ``. env/bin/activate``
* ``pip install -r requirements.txt``
* ``python setup.py develop``

.. _`repository`: https://github.com/fabric/fabric

.. _running-tests:

Running Tests
=============

Once your virtualenv is activated (``. env/bin/activate``) & you have the latest
requirements, running tests is just::

    pytest

You should **always** run tests on ``master`` (or the release branch you're
working with) to ensure they're passing before working on your own
changes/tests.

Alternatively, if you've run ``python setup.py develop`` on your Fabric clone,
you can also run::

    fab test

which is the same thing with ``-v`` added, followed by a second pass over
``fabric`` itself to pick up the handful of doctests living outside
``testpaths``.

To run the integration suite (which needs passwordless SSH to the host you
name) use::

    fab -H localhost test:integration

``fab test`` runs pytest *inside* the ``fab`` process rather than shelling out,
because ``-H`` sets the target host in that process only and the integration
tests connect using it directly.

.. note::
    Output capturing is turned off (``--capture=no`` in ``setup.cfg``). The
    suite replaces ``sys.stdout``/``sys.stderr`` itself and runs a real SSH
    server on localhost, neither of which survives pytest's capturing.

The mocking library, `fudge <http://farmdev.com/projects/fudge/index.html>`_,
is **vendored** under ``tests/_vendor/fudge`` rather than installed -- it is
Python 2 source that relied on ``2to3`` running at install time, which is no
longer possible. See ``tests/_vendor/README.md``.
