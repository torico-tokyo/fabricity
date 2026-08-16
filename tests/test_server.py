"""
Tests for the test server itself.

Not intended to be run by the greater test suite, only by specifically
targeting it on the command-line. Rationale: not really testing Fabric itself,
no need to pollute Fab's own test suite. (Yes, if these tests fail, it's likely
that the Fabric tests using the test server may also have issues, but still.)
"""


import pytest

from fabric.network import ssh

from server import FakeSFTPServer
from utils import eq_

__test__ = False


class AttrHolder(object):
    pass


@pytest.mark.parametrize('file_map, arg, expected', [
    pytest.param(
        {'file.txt': 'contents'},
        '',
        ['file.txt'],
        id="Single file",
    ),
    pytest.param(
        {'/file.txt': 'contents'},
        '/',
        ['file.txt'],
        id="Single absolute file",
    ),
    pytest.param(
        {'file1.txt': 'contents', 'file2.txt': 'contents2'},
        '',
        ['file1.txt', 'file2.txt'],
        id="Multiple files",
    ),
    pytest.param(
        {'folder': None},
        '',
        ['folder'],
        id="Single empty folder",
    ),
    pytest.param(
        {'folder': None, 'folder/subfolder': None},
        '',
        ['folder'],
        id="Empty subfolders",
    ),
    pytest.param(
        {'folder/subfolder/subfolder2/file.txt': 'contents'},
        "folder/subfolder/subfolder2",
        ['file.txt'],
        id="Non-empty sub-subfolder",
    ),
    pytest.param(
        {
            'file.txt': 'contents',
            'file2.txt': 'contents2',
            'folder/file3.txt': 'contents3',
            'empty_folder': None
        },
        '',
        ['file.txt', 'file2.txt', 'folder', 'empty_folder'],
        id="Mixed files, folders empty and non-empty, in homedir",
    ),
    pytest.param(
        {
            'file.txt': 'contents',
            'file2.txt': 'contents2',
            'folder/file3.txt': 'contents3',
            'folder/subfolder/file4.txt': 'contents4',
            'empty_folder': None
        },
        "folder",
        ['file3.txt', 'subfolder'],
        id="Mixed files, folders empty and non-empty, in subdir",
    ),
])
def test_list_folder(file_map, arg, expected):
    # Pass in fake server obj. (Can't easily clean up API to be more
    # testable since it's all implementing 'ssh' interface stuff.)
    server = AttrHolder()
    server.files = file_map
    interface = FakeSFTPServer(server)
    results = interface.list_folder(arg)
    # In this particular suite of tests, all results should be a file list,
    # not "no files found"
    assert results != ssh.SFTP_NO_SUCH_FILE
    # Grab filename from SFTPAttribute objects in result
    output = map(lambda x: x.filename, results)
    eq_(set(expected), set(output))
