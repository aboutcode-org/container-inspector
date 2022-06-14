#
# Copyright (c) nexB Inc. and others. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
# See http://www.apache.org/licenses/LICENSE-2.0 for the license text.
# See https://github.com/nexB/container-inspector for support or download.
# See https://aboutcode.org for more information about nexB OSS projects.
#

import os

from commoncode import fileutils
from commoncode import testcase

from container_inspector import utils


def check_files(target_dir, expected):
    """
    Walk test_dir.
    Check that all dirs are readable.
    Check that all files are:
     * non-special,
     * readable,
     * have a posix path that ends with one of the expected tuple paths.
    """
    result = []

    test_dir_path = fileutils.as_posixpath(target_dir)
    for top, _, files in os.walk(target_dir):
        for f in files:
            location = os.path.join(top, f)
            path = fileutils.as_posixpath(location)
            path = path.replace(test_dir_path, '').strip('/')
            result.append(path)

    expected_content = sorted(expected)
    result = sorted(result)

    assert result == expected_content


class TestUtils(testcase.FileBasedTesting):
    test_data_dir = os.path.join(os.path.dirname(__file__), 'data')

    def test_extract_tree_with_colon_in_filenames(self):
        expected = (
            'colon/libc6:amd64.list',
        )
        test_dir = self.get_test_loc('tar/colon.tar.xz')
        temp_dir = self.get_temp_dir()
        errors = utils.extract_tar(location=test_dir, target_dir=temp_dir)
        check_files(temp_dir, expected)
        assert not errors

    def test_extract_tar_relative(self):
        expected = ()
        test_dir = self.get_test_loc('tar/tar_relative.tar')
        temp_dir = self.get_temp_dir()
        errors = utils.extract_tar(location=test_dir, target_dir=temp_dir)
        check_files(temp_dir, expected)
        assert errors
        for error in errors:
            assert 'skipping unsupported' in error
            assert 'with relative path' in error

    def test_extract_tar_absolute(self):
        expected = (
            'tmp/subdir/a.txt',
            'tmp/subdir/b.txt',
        )
        test_dir = self.get_test_loc('tar/absolute_path.tar')
        temp_dir = self.get_temp_dir()
        errors = utils.extract_tar(location=test_dir, target_dir=temp_dir)
        check_files(temp_dir, expected)
        assert not errors
