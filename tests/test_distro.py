#
# Copyright (c) nexB Inc. and others. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
# See http://www.apache.org/licenses/LICENSE-2.0 for the license text.
# See https://github.com/nexB/container-inspector for support or download.
# See https://aboutcode.org for more information about nexB OSS projects.
#

import os

from commoncode.testcase import FileBasedTesting
from commoncode.fileutils import resource_iter

from container_inspector.distro import Distro
from container_inspector.distro import parse_os_release

from utilities import check_expected


class TestDistro(FileBasedTesting):
    test_data_dir = os.path.join(os.path.dirname(__file__), 'data')

    def test_parse_os_release(self):
        test_dir = self.get_test_loc('distro/os-release')

        for test_file in resource_iter(test_dir, with_dirs=False):
            if test_file.endswith('expected.json'):
                continue
            expected = test_file + '-expected.json'
            result = parse_os_release(test_file)
            check_expected(result, expected, regen=False)

    def test_distro_from_os_release_file(self):
        test_dir = self.get_test_loc('distro/os-release')

        for test_file in resource_iter(test_dir, with_dirs=False):
            if test_file.endswith('-expected.json'):
                continue
            expected = test_file + '-distro-expected.json'
            result = Distro.from_os_release_file(test_file).to_dict()
            check_expected(result, expected, regen=False)

    def test_distro_from_os_release_returns_None_on_empty_or_missing_location(self):
        assert Distro.from_os_release_file('') is None
        assert Distro.from_os_release_file(None) is None
        assert Distro.from_os_release_file('THIS/dir/does/exists') is None
        try:
            assert Distro.from_os_release_file(__file__) is None
            self.fail('An exception should be raised.')
        except:
            pass

    def test_distro_from_rootfs_returns_None_on_empty_or_missing_location(self):
        assert Distro.from_rootfs('') is None
        assert Distro.from_rootfs(None) is None
        assert Distro.from_rootfs('THIS/dir/does/exists') is None

    def test_distro_from_rootfs_returns_a_distro_even_if_not_found(self):
        not_a_rootfs = os.path.dirname(__file__)
        distro = Distro.from_rootfs(not_a_rootfs)
        # all distro attributes should be empty
        assert not distro

    def test_distro_from_rootfs_return_None_if_base_distro_not_found(self):
        base = Distro(os='freebsd', architecture='amd64')
        not_a_rootfs = os.path.dirname(__file__)
        distro = Distro.from_rootfs(not_a_rootfs, base_distro=base)
        assert distro is None

    def test_distro_does_not_default_to_linux(self):
        # we want to ensure that no attributes values contains linux by default
        distro = repr(Distro().to_dict().values()).lower()
        assert 'linux' not in distro

    def test_distro_from_rootfs_detects_windows(self):
        test_dir = self.extract_test_tar('distro/windows-container-rootfs.tar')
        distro = Distro.from_rootfs(test_dir)
        expected = {'identifier': 'windows', 'os': 'windows'}
        results = {k: v for k, v in sorted(distro.to_dict().items()) if v}
        assert results == expected

    def test_distro_from_rootfs_has_base_distro_merged(self):
        base = Distro(os='windows', architecture='amd64')
        test_dir = self.extract_test_tar('distro/windows-container-rootfs.tar')
        distro = Distro.from_rootfs(test_dir, base_distro=base)
        expected = {
            'architecture': 'amd64',
            'identifier': 'windows',
            'os': 'windows',
        }
        results = {k: v for k, v in sorted(distro.to_dict().items()) if v}
        assert results == expected

    def test_distro_from_rootfs_raise_exception_if_different_base_distro_os(self):
        base = Distro(os='freebsd')
        test_dir = self.extract_test_tar('distro/windows-container-rootfs.tar')
        try:
            Distro.from_rootfs(test_dir, base_distro=base)
        except Exception as e:
            assert str(e) == 'Inconsistent base distro OS: freebsd and found distro OS : windows'
