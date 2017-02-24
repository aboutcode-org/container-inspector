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

import os

from commoncode.testcase import FileBasedTesting

from conan.cli import collect_images_v10
from conan.cli import collect_and_rebuild_rootfs_v10


class TestDockerCli(FileBasedTesting):
    test_data_dir = os.path.join(os.path.dirname(__file__), 'data')

    def test_collect_images(self):
        test_dir = self.extract_test_tar('docker/v10_format/images.tgz')
        result = collect_images_v10(test_dir)
        assert len(result) == 3

    def test_collect_images_single(self):
        test_dir = self.extract_test_tar('docker/v10_format/busybox2.tgz')
        result = collect_images_v10(test_dir)
        assert len(result) == 1

    def test_collect_images_many(self):
        test_dir = self.extract_test_tar('docker/v10_format/merge.tgz')
        base = os.path.dirname(test_dir).strip('\\/')
        result = collect_images_v10(test_dir)
        result = [f.replace(base, '').lstrip('\\/') for f in result]
        expected = ['merge.tgz/merge/busybox', 'merge.tgz/merge/busybox2']
        assert sorted(expected) == sorted(result)

    def test_collect_and_rebuild_rootfs(self):
        test_dir = self.extract_test_tar('docker/v10_format/merge.tgz')
        print(test_dir)
        result = collect_and_rebuild_rootfs_v10(test_dir, echo=print)
        base = os.path.dirname(test_dir).strip('\\/')
        result = [(f.replace(base, '').lstrip('\\/'), set([w.replace(base, '').lstrip('\\/') for w in wo]),)
                    for f, wo in result.items()]
        expected = [
            ('merge.tgz/merge/busybox2',
             set(['merge.tgz/merge/busybox2-extract/proc',
              'merge.tgz/merge/busybox2-extract/opt',
              'merge.tgz/merge/busybox2-extract/usr',
              'merge.tgz/merge/busybox2-extract/root',
              'merge.tgz/merge/busybox2-extract/mnt',
              'merge.tgz/merge/busybox2-extract/sbin',
              'merge.tgz/merge/busybox2-extract/sys',
              'merge.tgz/merge/busybox2-extract/etc',
              'merge.tgz/merge/busybox2-extract/var',
              'merge.tgz/merge/busybox2-extract/dev',
              'merge.tgz/merge/busybox2-extract/tmp',
              'merge.tgz/merge/busybox2-extract/media',
              'merge.tgz/merge/busybox2-extract/home',
              'merge.tgz/merge/busybox2-extract/bin',
              'merge.tgz/merge/busybox2-extract/lib/libcrypt-0.9.33.2.so',
              'merge.tgz/merge/busybox2-extract/lib/ld64-uClibc-0.9.33.2.so',
              'merge.tgz/merge/busybox2-extract/lib/libdl-0.9.33.2.so']))
        ]
        assert expected == result
