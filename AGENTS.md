# AGENTS.md

Fabricity is a fork of Fabric 1.x (via Fabric3) kept working on current Python
and Paramiko releases. The public API is Fabric 1.x's and is expected to stay
that way: a fabfile written for Fabric 1.x must keep running. Prefer a fix that
preserves the existing behaviour over one that modernises the interface.

## Layout

| Path | Contents |
|---|---|
| `fabric/` | The library. `main.py` is the `fab` entry point, `operations.py` / `network.py` / `state.py` carry most of the behaviour. |
| `fabric/contrib/` | Higher-level helpers (`files`, `project`, `console`, `django`). |
| `tests/` | Unit tests. `tests/server.py` runs a real local SSH server. |
| `integration/` | Integration suite; connects over SSH and is not run by default. |
| `sites/` | Sphinx sources for the API docs (`sites/docs`) and the website (`sites/www`). |
| `fabfile.py` | This project's own fabfile (`test`, `upload`). |
| `tasks.py` | Invoke tasks for the docs and release builds. |

## Setup

Dependencies are managed with [uv](https://docs.astral.sh/uv/). The dev venv is
Python 3.13 (`.python-version`); the package itself supports 3.9+.

```shell
uv sync
```

## Tests

```shell
uv run pytest                      # the whole suite (~2.5 minutes)
uv run pytest tests/test_utils.py  # one file
uv run fab test                    # pytest plus the doctests in fabric/
uv run fab -H localhost test:integration   # integration suite
```

Notes that bite:

- Output capturing is disabled in `pyproject.toml`. The suite replaces
  `sys.stdout` / `sys.stderr` itself and runs a real SSH server, neither of
  which survives pytest's capturing. Do not re-enable it.
- The suite binds a local port for that SSH server, so it fails in an
  environment that forbids binding.
- `tests/test_context_managers.py::TestQuietAndWarnOnly::test_quiet_hides_all_output`
  is timing-sensitive and fails occasionally under load. Re-run before
  investigating.
- New tests use the `# Arrange` / `# Act` / `# Assert` layout.

## Docs

```shell
uv run invoke docs   # sites/docs -> API documentation
uv run invoke www    # sites/www  -> the website
```

## Style

- `setup.cfg` holds a flake8 config, but flake8 is not a dependency; run it with
  `uvx flake8`. The existing code has many violations (long lines, lambdas
  assigned to names, references to `unicode`). Do not reformat untouched code to
  clear them — just avoid adding new ones in the lines you touch.
- Comments and docstrings are English.
- Python 2 compatibility shims (`from __future__ import ...`, `six`) are still
  present throughout. Removing them is a separate, deliberate task, not
  something to do in passing.
- Comments should carry the non-obvious *why*. The surrounding code follows
  this: see `fabric/network.py` on why DSS keys are gone, or `pyproject.toml`
  on why each dependency bound is where it is.

## Release

1. Bump `VERSION` in `fabric/version.py` (a tuple, e.g. `(1, 16, 0, 'final', 0)`).
2. `rm -rf dist && uv build`
3. Upload `dist/*` to PyPI with twine. Requires the maintainer's credentials.

`sites/www/changelog.rst` stopped being updated upstream at 1.14.0 and is not
maintained here; do not add entries to it.

There are no GitHub Actions workflows. `.travis.yml` is kept current (it runs
the matrix from 3.9 to 3.14), but whether Travis still builds this repository is
not something the repository can tell you — treat the local run as the check
that matters. Its `script:` section is the canonical full sequence:

```shell
uv run fab test
uv run fab -H localhost test:integration
uv run invoke www
uv run invoke docs -o -W
uv run invoke www -c -o -W
```
