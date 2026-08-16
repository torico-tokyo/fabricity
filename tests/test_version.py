"""
Tests covering Fabric's version number pretty-print functionality.
"""

import pytest

import fabric.version


@pytest.mark.parametrize('tup, short, normal, verbose', [
    ((0, 9, 0, 'final', 0), '0.9.0', '0.9', '0.9 final'),
    ((0, 9, 1, 'final', 0), '0.9.1', '0.9.1', '0.9.1 final'),
    ((0, 9, 0, 'alpha', 1), '0.9a1', '0.9 alpha 1', '0.9 alpha 1'),
    ((0, 9, 1, 'beta', 1), '0.9.1b1', '0.9.1 beta 1', '0.9.1 beta 1'),
    ((0, 9, 0, 'release candidate', 1),
        '0.9rc1', '0.9 release candidate 1', '0.9 release candidate 1'),
    ((1, 0, 0, 'alpha', 0), '1.0a', '1.0 pre-alpha', '1.0 pre-alpha'),
])
def test_get_version(tup, short, normal, verbose):
    get_version = fabric.version.get_version
    previous = fabric.version.VERSION
    fabric.version.VERSION = tup
    try:
        assert get_version('short') == short
        assert get_version('normal') == normal
        assert get_version('verbose') == verbose
    finally:
        fabric.version.VERSION = previous
