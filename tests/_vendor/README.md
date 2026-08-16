# Vendored third-party test dependencies

## fudge 1.1.1

`fudge/` is a vendored copy of [fudge](https://pypi.org/project/fudge/) 1.1.1
(MIT licensed -- the full text is kept alongside it in `fudge/LICENSE.txt`),
used by the test suite as its mocking library.

**Why it is vendored:** fudge 1.1.1 (released 2019, unmaintained) ships Python 2
source and relies on setuptools running `2to3` *at install time*. That path is
gone twice over:

* setuptools removed `use_2to3` in 58.0.0, so the sdist fails to build with any
  modern setuptools (`error in fudge setup command: use_2to3 is invalid`).
* `lib2to3` itself was removed from the standard library in Python 3.13, so the
  conversion cannot be performed at all on the versions we target.

There is no maintained Python 3 fork on PyPI, so `pip install fudge` can never
succeed on a supported interpreter. Vendoring the already-converted source is
what makes the suite runnable.

**How this copy was produced:**

1. `fudge-1.1.1.tar.gz` from PyPI.
2. `python3.12 -m lib2to3 -w -n --no-diffs fudge/` (3.12 is the last version
   that still ships `lib2to3`).
3. `import thread` → `import _thread` (done by 2to3) — `_thread.get_ident()` is
   used for the per-thread call registry.
4. `fudge/tests/` dropped; it is fudge's own suite and not needed here.

No other edits. `tests/conftest.py` puts this directory on `sys.path` so that
`import fudge` resolves to this copy.

**Long term** the suite should move off fudge and onto `unittest.mock`
(TORICO-DEV-73 follow-up). Vendoring is what gives that migration a green
baseline to verify against — before it, the suite could not run at all.
