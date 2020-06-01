# Copyright (c) nexB Inc. and others. All rights reserved.
# http://nexb.com and https://github.com/nexB/conan/
#
# This software is licensed under the Apache License version 2.0.#
#
# You may not use this software except in compliance with the License.
# You may obtain a copy of the License at:
#     http://apache.org/licenses/LICENSE-2.0
# Unless required by applicable law or agreed to in writing, software distributed
# under the License is distributed on an "AS IS" BASIS, WITHOUT WARRANTIES OR
# CONDITIONS OF ANY KIND, either express or implied. See the License for the
# specific language governing permissions and limitations under the License.


from __future__ import print_function
from __future__ import absolute_import
from __future__ import unicode_literals

import os

from commoncode.testcase import FileBasedTesting

from conan import cli
from unittest.case import expectedFailure
from commoncode import fileutils


@expectedFailure
class TestDockerCliV10(FileBasedTesting):
    test_data_dir = os.path.join(os.path.dirname(__file__), 'data')

    def test_collect_images_v10(self):
        test_dir = self.extract_test_tar('docker/v10_format/images.tgz')
        result = cli.conan(test_dir)
        assert len(result) == 3

    def test_collect_images_single_v10(self):
        test_dir = self.extract_test_tar('docker/v10_format/busybox2.tgz')
        result = cli.conan(test_dir)
        assert len(result) == 1

    def test_collect_images_many_v10(self):
        test_dir = self.extract_test_tar('docker/v10_format/merge.tgz')
        base = os.path.dirname(test_dir).strip('\\/')
        result = cli.conan(test_dir)
        result = [f.replace(base, '').lstrip('\\/') for f in result]
        expected = ['merge.tgz/merge/busybox', 'merge.tgz/merge/busybox2']
        assert sorted(expected) == sorted(result)


class TestSquashCliV10(FileBasedTesting):
    test_data_dir = os.path.join(os.path.dirname(__file__), 'data')

    @expectedFailure
    def test_collect_and_rebuild_rootfs_single_layer(self):
        test_dir = self.extract_test_tar('repos/hello-world.tar')
        target_dir = self.get_temp_dir()

        cli._conan_squash(
            image_directory=test_dir, 
            extract_directory=target_dir)
        
        results = sorted(f.replace(target_dir, '') for f in
            fileutils.resource_iter(location=target_dir, with_dirs=False))
        expected = [
            '/proc',
            '/opt',
            '/usr',
            '/root',
            '/mnt',
            '/sbin',
            '/sys',
            '/etc',
            '/var',
            '/dev',
            '/tmp',
            '/media',
            '/home',
            '/bin',
            '/lib/libcrypt-0.9.33.2.so',
            '/lib/ld64-uClibc-0.9.33.2.so',
            '/lib/libdl-0.9.33.2.so',
        ]
        assert expected == results
