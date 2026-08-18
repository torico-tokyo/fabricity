Fabricity
=========

.. begin-description

Fabricity is a Python library and command-line tool for streamlining the use of
SSH for application deployment or systems administration tasks. It keeps the
Fabric 1.x API working on current Python releases.

It provides a basic suite of operations for executing local or remote shell
commands (normally or via ``sudo``) and uploading/downloading files, as well as
auxiliary functionality such as prompting the running user for input, or
aborting execution.

Typical use involves creating a Python module containing one or more functions,
then executing them via the ``fab`` command-line tool. Below is a small but
complete "fabfile" containing a single task:

.. code-block:: python

    from fabric.api import run

    def host_type():
        run('uname -s')

If you save the above as ``fabfile.py`` (the default module that ``fab``
loads), you can run the tasks defined in it on one or more servers, like so::

    $ fab -H localhost,linuxbox host_type
    [localhost] run: uname -s
    [localhost] out: Darwin
    [linuxbox] run: uname -s
    [linuxbox] out: Linux

    Done.
    Disconnecting from localhost... done.
    Disconnecting from linuxbox... done.

In addition to use via the ``fab`` tool, Fabricity's components may be imported
into other Python code, providing a Pythonic interface to the SSH protocol
suite at a higher level than that provided by e.g. the Paramiko library (which
Fabricity itself uses).

Where it comes from
===================

Fabricity is a fork of `Fabric3 <https://github.com/mathiasertl/fabric>`_,
which in turn forked `Fabric <https://github.com/fabric/fabric>`_ 1.x to add
Python 3 support. Fabric3 was retired once mainline Fabric shipped Python 3
support, but mainline Fabric 2+ is a different tool with an incompatible API, so
a codebase with an existing Fabric 1.x fabfile has nowhere to move to. Fabricity
is that place: the same API, kept working on current Python and Paramiko
releases.

Installation
============

Fabricity installs the same ``fabric`` package and ``fab`` command as Fabric, so
any other Fabric distribution has to go first — uninstalling one afterwards
deletes the files Fabricity has since taken over::

    pip uninstall Fabric Fabric3
    pip install fabricity

Requires Python 3.9 or later.

Differences with Fabric 1.x
===========================

Fabricity aims to be a drop-in replacement for Fabric 1.x. Known differences:

* Python 2 is no longer supported.
* ``fabric.utils.RingBuffer`` is removed; use ``collections.deque`` from the
  standard library instead.
* On Python 3 the ``contextlib.nested`` replacement is implemented with
  ``contextlib.ExitStack``. It was removed from the standard library for good
  reason; using it is not encouraged.
* DSS/DSA keys are not supported. Paramiko 4 removed ``paramiko.dsskey``;
  ``env.key`` accepts Ed25519, ECDSA and RSA keys.
* The 3des-cbc cipher is not offered by default. Set ``env.disabled_algorithms``
  to override.

Documentation
=============

The Fabric 1.x usage and API documentation at `docs.fabfile.org/en/1.14
<https://docs.fabfile.org/en/1.14/>`_ applies to Fabricity, apart from the
differences listed above. The sources for the same documentation live in
``sites/`` in this repository. Note that the current ``fabfile.org`` covers
mainline Fabric 2+, which is a different API.

Development
===========

Dependencies are managed with `uv <https://docs.astral.sh/uv/>`_::

    uv sync
    uv run pytest

``AGENTS.md`` in this repository carries the full set of development commands.
