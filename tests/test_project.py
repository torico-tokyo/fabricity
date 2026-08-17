import unittest
import os

from unittest import mock

from fabric.contrib import project


class UploadProjectTestCase(unittest.TestCase):
    """Test case for :func: `fabric.contrib.project.upload_project`."""

    fake_tmp = "testtempfolder"


    def setUp(self):
        # We need to mock out run, local, and put
        self.patchers = []
        for name in ('run', 'local', 'put'):
            patcher = mock.patch.object(project, name)
            self.patchers.append(patcher)
            setattr(self, 'fake_%s' % name, patcher.start())

        # We don't want to create temp folders
        mkdtemp_patcher = mock.patch.object(
            project, 'mkdtemp', return_value=self.fake_tmp
        )
        self.patchers.append(mkdtemp_patcher)
        self.fake_mkdtemp = mkdtemp_patcher.start()


    def tearDown(self):
        for patcher in reversed(self.patchers):
            patcher.stop()


    def archive_command(self):
        """
        Return the command upload_project() used to build the tarball.

        upload_project() calls local() twice -- once to create the archive and
        once to clean the temp dir up -- and it is always the first one that
        builds the archive, so these tests can assert against it exactly
        rather than searching for a call that happens to match.
        """
        assert self.fake_local.call_args_list, "local() was never called"
        return self.fake_local.call_args_list[0][0][0]


    def test_temp_folder_is_used(self):
        """A unique temp folder is used for creating the archive to upload."""

        # Exercise
        project.upload_project()

        self.fake_mkdtemp.assert_called_once()


    def test_project_is_archived_locally(self):
        """The project should be archived locally before being uploaded."""

        # Exercise
        project.upload_project()

        assert self.archive_command().startswith("tar -czf")


    def test_current_directory_is_uploaded_by_default(self):
        """By default the project uploaded is the current working directory."""

        cwd_path, cwd_name = os.path.split(os.getcwd())

        # Exercise
        project.upload_project()

        assert self.archive_command().endswith(
            "-C %s %s" % (cwd_path, cwd_name)
        )


    def test_path_to_local_project_can_be_specified(self):
        """It should be possible to specify which local folder to upload."""

        project_path = "path/to/my/project"

        # Exercise
        project.upload_project(local_dir=project_path)

        assert self.archive_command().endswith("-C path/to/my project")


    def test_path_to_local_project_no_separator(self):
        """Local folder can have no path separator (in current directory)."""

        project_path = "testpath"

        # Exercise
        project.upload_project(local_dir=project_path)

        assert self.archive_command().endswith("-C . testpath")


    def test_path_to_local_project_can_end_in_separator(self):
        """A local path ending in a separator should be handled correctly."""

        project_path = "path/to/my"
        base = "project"

        # Exercise
        project.upload_project(local_dir="%s/%s/" % (project_path, base))

        assert self.archive_command().endswith(
            "-C %s %s" % (project_path, base)
        )


    def test_default_remote_folder_is_home(self):
        """Project is uploaded to remote home by default."""

        local_dir = "folder"

        # Exercise
        project.upload_project(local_dir=local_dir)

        self.fake_put.assert_called_once_with(
            "%s/folder.tar.gz" % self.fake_tmp, "folder.tar.gz", use_sudo=False
        )


    def test_path_to_remote_folder_can_be_specified(self):
        """It should be possible to specify which local folder to upload to."""

        local_dir = "folder"
        remote_path = "path/to/remote/folder"

        # Exercise
        project.upload_project(local_dir=local_dir, remote_dir=remote_path)

        self.fake_put.assert_called_once_with(
            "%s/folder.tar.gz" % self.fake_tmp,
            "%s/folder.tar.gz" % remote_path,
            use_sudo=False,
        )
