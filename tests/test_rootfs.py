# Copyright (c) 2017 nexB Inc. and others. All rights reserved.
# http://nexb.com and https://github.com/pombredanne/conan/
# The Conan software is licensed under the Apache License version 2.0.
# Data generated with Conan require an acknowledgment.
# Conan is a trademark of nexB Inc.
#
# You may not use this software except in compliance with the License.
# You may obtain a copy of the License at: http://apache.org/licenses/LICENSE-2.0
# Unless required by applicable law or agreed to in writing, software distributed
# under the License is distributed on an "AS IS" BASIS, WITHOUT WARRANTIES OR
# CONDITIONS OF ANY KIND, either express or implied. See the License for the
# specific language governing permissions and limitations under the License.

from __future__ import print_function
from __future__ import absolute_import
from __future__ import unicode_literals

from collections import OrderedDict
import os

from commoncode import testcase
from commoncode.testcase import FileBasedTesting
from commoncode import fileutils

from conan import image_v10
from conan.rootfs import rebuild_rootfs
from conan.rootfs import InconsistentLayersError


class TestRootfs(FileBasedTesting):
    test_data_dir = os.path.join(os.path.dirname(__file__), 'data')

    def test_rebuild_rootfs_format_v10(self):
        test_dir = self.extract_test_tar('docker/v10_format/busybox.tgz')
        image = image_v10.ImageV10(test_dir)
        target_dir = self.get_temp_dir()
        rebuild_rootfs(image, target_dir)
        expected = self.extract_test_tar('docker/v10_format/check_busybox_layer.tar')
        assert testcase.is_same(target_dir, expected)

    def test_rebuild_rootfs_format_v10_without_repositories_file(self):
        test_dir = self.extract_test_tar('docker/v10_format/busybox_no_repo.tgz')
        image = image_v10.ImageV10(test_dir)
        target_dir = self.get_temp_dir()
        rebuild_rootfs(image, target_dir)
        expected = self.extract_test_tar('docker/v10_format/check_busybox_layer.tar')
        assert testcase.is_same(target_dir, expected)

    def test_rebuild_rootfs_format_v10_with_delete(self):
        test_dir = self.extract_test_tar('docker/v10_format/busybox2.tgz')
        image = image_v10.ImageV10(test_dir)
        target_dir = self.get_temp_dir()
        rebuild_rootfs(image, target_dir)
        expected = [
            '/lib/librt-0.9.33.2.so',
            '/lib/libgcc_s.so.1',
            '/lib/libutil-0.9.33.2.so',
            '/lib/libuClibc-0.9.33.2.so',
            '/lib/libm-0.9.33.2.so',
            '/lib/libresolv-0.9.33.2.so',
            '/lib/libnsl-0.9.33.2.so',
            '/lib/libpthread-0.9.33.2.so'
        ]
        assert sorted(expected) == sorted(f.replace(target_dir, '') for f in fileutils.file_iter(target_dir))

    def test_rebuild_rootfs_format_v10_with_delete_with_out_of_order_layers(self):
        test_dir = self.extract_test_tar('docker/v10_format/busybox2.tgz')
        image = image_v10.ImageV10(test_dir)

        # shuffle artificially the layer order
        image.layers = OrderedDict(sorted(image.layers.items()))

        target_dir = self.get_temp_dir()
        try:
            rebuild_rootfs(image, target_dir)
        except InconsistentLayersError:
            pass
