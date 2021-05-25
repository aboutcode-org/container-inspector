# Copyright (c) nexB Inc. and others. All rights reserved.
# http://nexb.com and https://github.com/nexB/container-inspector/
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

import os

from commoncode import fileutils
from commoncode import testcase

from container_inspector import image
from container_inspector.rootfs import rebuild_rootfs
from container_inspector import rootfs


class TestRootfs(testcase.FileBasedTesting):
    test_data_dir = os.path.join(os.path.dirname(__file__), 'data')

    def test_rebuild_rootfs_simple(self):
        test_dir = self.extract_test_tar('rootfs/hello-world.tar')
        img = image.Image.get_images_from_dir(test_dir)[0]
        target_dir = self.get_temp_dir()
        rebuild_rootfs(img, target_dir)
        results = sorted([p.replace(target_dir, '')
            for p in fileutils.resource_iter(target_dir)])
        expected = ['/hello']
        assert expected == results

    def test_image_squash_simple(self):
        test_dir = self.extract_test_tar('rootfs/hello-world.tar')
        img = image.Image.get_images_from_dir(test_dir)[0]
        target_dir = self.get_temp_dir()
        img.squash(target_dir)
        results = sorted([p.replace(target_dir, '')
            for p in fileutils.resource_iter(target_dir)])
        expected = ['/hello']
        assert expected == results

    def test_rebuild_rootfs_with_delete(self):
        test_dir = self.extract_test_tar('rootfs/she-image_from_scratch-1.0.tar')
        img = image.Image.get_images_from_dir(test_dir)[0]
        target_dir = self.get_temp_dir()
        rebuild_rootfs(img, target_dir)
        results = sorted([p.replace(target_dir, '')
            for p in fileutils.resource_iter(target_dir)])
        expected = [
            '/additions',
            '/additions/bar',
            '/additions/baz',
            '/additions/baz/this',
            '/additions/foo',
            '/additions/hello',
            '/hello',
        ]
        assert expected == results

    def test_rebuild_rootfs_multilayers(self):
        test_dir = self.extract_test_tar('rootfs/imagesv11.tar')
        target_dir = self.get_temp_dir()

        for img in image.Image.get_images_from_dir(test_dir):
            rebuild_rootfs(img, target_dir)

        results = sorted([p.replace(target_dir, '')
            for p in fileutils.resource_iter(target_dir, with_dirs=False)])
        expected = [
            '/bin/busybox',
            '/etc/fstab',
            '/etc/group',
            '/etc/hostname',
            '/etc/hosts',
            '/etc/init.d/S01logging',
            '/etc/init.d/S20urandom',
            '/etc/init.d/S40network',
            '/etc/init.d/rcK',
            '/etc/init.d/rcS',
            '/etc/inittab',
            '/etc/inputrc',
            '/etc/iproute2/ematch_map',
            '/etc/iproute2/group',
            '/etc/iproute2/rt_dsfield',
            '/etc/iproute2/rt_protos',
            '/etc/iproute2/rt_realms',
            '/etc/iproute2/rt_scopes',
            '/etc/iproute2/rt_tables',
            '/etc/issue',
            '/etc/ld.so.conf',
            '/etc/network/interfaces',
            '/etc/nsswitch.conf',
            '/etc/os-release',
            '/etc/passwd',
            '/etc/profile',
            '/etc/protocols',
            '/etc/random-seed',
            '/etc/securetty',
            '/etc/services',
            '/etc/shadow',
            '/hello',
            '/lib/ld64-uClibc-0.9.33.2.so',
            '/lib/libcrypt-0.9.33.2.so',
            '/lib/libdl-0.9.33.2.so',
            '/lib/libgcc_s.so.1',
            '/lib/libm-0.9.33.2.so',
            '/lib/libnsl-0.9.33.2.so',
            '/lib/libpthread-0.9.33.2.so',
            '/lib/libresolv-0.9.33.2.so',
            '/lib/librt-0.9.33.2.so',
            '/lib/libuClibc-0.9.33.2.so',
            '/lib/libutil-0.9.33.2.so',
            '/root/.bash_history',
            '/root/.bash_logout',
            '/root/.bash_profile',
            '/sbin/bridge',
            '/sbin/genl',
            '/sbin/ifstat',
            '/sbin/ip',
            '/sbin/ldconfig',
            '/sbin/lnstat',
            '/sbin/nstat',
            '/sbin/routef',
            '/sbin/routel',
            '/sbin/rtacct',
            '/sbin/rtmon',
            '/sbin/rtpr',
            '/sbin/ss',
            '/sbin/tc',
            '/usr/bin/getconf',
            '/usr/bin/ldd',
            '/usr/lib/libip4tc.so.0.1.0',
            '/usr/lib/libiptc.so.0.0.0',
            '/usr/lib/libxtables.so.10.0.0',
            '/usr/lib/tc/experimental.dist',
            '/usr/lib/tc/m_xt.so',
            '/usr/lib/tc/normal.dist',
            '/usr/lib/tc/pareto.dist',
            '/usr/lib/tc/paretonormal.dist',
            '/usr/sbin/xtables-multi',
            '/usr/share/udhcpc/default.script',
        ]
        assert expected == results

    def test_rootfs_can_find_whiteouts(self):

        def mock_walker(root):
            opj = os.path.join
            return [
                (root, ['bin', 'usr'], []),
                (opj(root, 'bin'), [], ['.wh..wh.opq']),
                (opj(root, 'usr'), ['lib'], ['foo', '.wh.bar']),
            ]

        results = list(rootfs.find_whiteouts('baz', walker=mock_walker))
        expected = [
            ('baz/bin/.wh..wh.opq', 'bin'),
            ('baz/usr/.wh.bar', 'usr/bar'),
        ]
        assert results == expected

    def test_rootfs_can_find_whiteouts_none(self):

        def mock_walker(root):
            return [
                (root, ['bin', 'usr'], []),
                (os.path.join(root, 'usr'), ['lib'], ['foo', 'bar']),
            ]

        results = list(rootfs.find_whiteouts('baz', walker=mock_walker))
        assert results == []

    def test_rootfs_can_find_root(self):

        def mock_walker(root):
            return [
                (root, ['bin', 'usr'], []),
                (os.path.join(root, 'usr'), ['lib'], ['foo', 'bar']),
            ]

        assert rootfs.find_root('baz', walker=mock_walker) == 'baz'

    def test_rootfs_can_find_no_root(self):

        def mock_walker(root):
            return [
                (root, ['abin', 'ausr'], []),
                (os.path.join(root, 'usr'), ['lib'], ['foo', 'bar']),
            ]

        assert rootfs.find_root('baz', walker=mock_walker) is None

    def test_rootfs_can_find_no_root_with_single_match(self):

        def mock_walker(root):
            return [
                (root, ['bin', 'ausr'], []),
                (os.path.join(root, 'usr'), ['lib'], ['foo', 'bar']),
            ]

        assert rootfs.find_root('baz', walker=mock_walker) is None

    def test_rootfs_does_respects_max_depth(self):
        test_dir = self.extract_test_tar('rootfs/find_root.tar.gz')
        assert not rootfs.find_root(test_dir, max_depth=1)
        assert not rootfs.find_root(test_dir, max_depth=2)
        assert not rootfs.find_root(test_dir, max_depth=3)
        assert not rootfs.find_root(test_dir, max_depth=4)

        expected = '/find_root/level1/level2/level3'
        found = rootfs.find_root(test_dir, max_depth=5)
        assert found.replace(test_dir, '') == expected

        found = rootfs.find_root(test_dir, max_depth=0)
        assert found.replace(test_dir, '') == expected

        found = rootfs.find_root(os.path.join(test_dir, 'find_root'), max_depth=4)
        assert found.replace(test_dir, '') == expected
