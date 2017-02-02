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

from __future__ import absolute_import, print_function

from collections import OrderedDict
import os

from commoncode import testcase
from commoncode.testcase import FileBasedTesting
from commoncode import fileutils

from conan import docker
from conan.docker import LayerOld
from conan.docker import NonSortableLayersError
from conan.cli import collect_images
from conan.utils import rebuild_rootfs
from conan import InconsistentLayersOderingError
from conan.cli import collect_and_rebuild_rootfs
from conan.dockerfile import normalized_layer_command
from conan.utils import find_shortest_prefix_length


class TestDockerCli(FileBasedTesting):
    test_data_dir = os.path.join(os.path.dirname(__file__), 'data')

    def test_collect_images(self):
        test_dir = self.extract_test_tar('docker/v10_format/images.tgz')
        result = collect_images(test_dir)
        assert len(result) == 3

    def test_collect_images_single(self):
        test_dir = self.extract_test_tar('docker/v10_format/busybox2.tgz')
        result = collect_images(test_dir)
        assert len(result) == 1

    def test_collect_images_many(self):
        test_dir = self.extract_test_tar('docker/v10_format/merge.tgz')
        base = os.path.dirname(test_dir).strip('\\/')
        result = collect_images(test_dir)
        result = [f.replace(base, '').lstrip('\\/') for f in result]
        expected = ['merge.tgz/merge/busybox', 'merge.tgz/merge/busybox2']
        assert sorted(expected) == sorted(result)

    def test_collect_and_rebuild_rootfs(self):
        test_dir = self.extract_test_tar('docker/v10_format/merge.tgz')
        print(test_dir)
        result = collect_and_rebuild_rootfs(test_dir, echo=print)
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


class TestDockerFormat10(FileBasedTesting):
    test_data_dir = os.path.join(os.path.dirname(__file__), 'data')

    def test_ImageV10(self):
        test_dir = self.extract_test_tar('docker/v10_format/busybox.tgz')
        docker.ImageV10(test_dir)

    def test_ImageV10_without_repositories_file(self):
        test_dir = self.extract_test_tar('docker/v10_format/busybox_no_repo.tgz')
        assert docker.ImageV10(test_dir)


class TestDockerUtils(FileBasedTesting):
    test_data_dir = os.path.join(os.path.dirname(__file__), 'data')

    def test_rebuild_rootfs_format_v10(self):
        test_dir = self.extract_test_tar('docker/v10_format/busybox.tgz')
        image = docker.ImageV10(test_dir)
        target_dir = self.get_temp_dir()
        rebuild_rootfs(image, target_dir)
        expected = self.extract_test_tar('docker/v10_format/check_busybox_layer.tar')
        assert testcase.is_same(target_dir, expected)

    def test_rebuild_rootfs_format_v10_without_repositories_file(self):
        test_dir = self.extract_test_tar('docker/v10_format/busybox_no_repo.tgz')
        image = docker.ImageV10(test_dir)
        target_dir = self.get_temp_dir()
        rebuild_rootfs(image, target_dir)
        expected = self.extract_test_tar('docker/v10_format/check_busybox_layer.tar')
        assert testcase.is_same(target_dir, expected)

    def test_rebuild_rootfs_format_v10_with_delete(self):
        test_dir = self.extract_test_tar('docker/v10_format/busybox2.tgz')
        image = docker.ImageV10(test_dir)
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

    def test_find_shortest_prefix_length(self):
        strings = [
            '766dd2d9abcf5a4cc87729e938c005b0714309659b197fca61e4fd9b775b6b7b',
            'c89045c0bfe8cd62c539d0cc227eaeab7f5445002b8a711c0d5f47ec7716ad51',
            '045df3e66e28eadb9be8c9156f638a4f9cfe286a696dd06sadasdadas41153e0d76e3e6af1',
            '3fc782251abe2cf96c2b1f95d3e4d20396774fa6522ec0e45a6cbf8e27edc381',
            '0c752394b855e8f15d2dc1fba6f10f4386ff6c0ab6fc6a253285bcfbfdd214sdaasdasdaf5',
            '34e94e67e63a0f079d9336b3c2a52e814d138e5b3f1f614a0cfe273814ed7c0a',
            '511136ea3c5a64f264b78b5433614aec563103b4d4702f3ba7d4d2698e22c158',
        ]
        assert 2 == find_shortest_prefix_length(strings)

    def test_find_shortest_prefix_length_2(self):
        strings = [
            '766dd2d9abcf5a4cc87729e938c005b0714309659b197fca61e4fd9b775b6b7b',
            '7c89045c0bfe8cd62c539d0cc227eaeab7f5445002b8a711c0d5f47ec7716ad51',
            '7045df3e66e28eadb9be8c9156f638a4f9cfe286a696dd06sadasdadas41153e0d76e3e6af1',
            '73fc782251abe2cf96c2b1f95d3e4d20396774fa6522ec0e45a6cbf8e27edc381',
            '70c752394b855e8f15d2dc1fba6f10f4386ff6c0ab6fc6a253285bcfbfdd214sdaasdasdaf5',
            '734e94e67e63a0f079d9336b3c2a52e814d138e5b3f1f614a0cfe273814ed7c0a',
            '7511136ea3c5a64f264b78b5433614aec563103b4d4702f3ba7d4d2698e22c158',
        ]
        assert 3 == find_shortest_prefix_length(strings)

    def test_rebuild_rootfs_format_v10_with_delete_with_out_of_order_layers(self):
        test_dir = self.extract_test_tar('docker/v10_format/busybox2.tgz')
        image = docker.ImageV10(test_dir)

        # shuffle artificially the layer order
        image.layers = OrderedDict(sorted(image.layers.items()))

        target_dir = self.get_temp_dir()
        try:
            rebuild_rootfs(image, target_dir)
        except InconsistentLayersOderingError:
            pass


class TestDockerLayerOld(FileBasedTesting):
    test_data_dir = os.path.join(os.path.dirname(__file__), 'data')

    def test_LayerOld_sort(self):
        # ordered in correct layer order, top to bottom
        test_data = [
            ('511136ea3c5a64f264b78b5433614aec563103b4d4702f3ba7d4d2698e22c158', {'parent': None}),
            ('34e94e67e63a0f079d9336b3c2a52e814d138e5b3f1f614a0cfe273814ed7c0a', {'parent': '511136ea3c5a64f264b78b5433614aec563103b4d4702f3ba7d4d2698e22c158'}),
            ('0c752394b855e8f15d2dc1fba6f10f4386ff6c0ab6fc6a253285bcfbfdd214f5', {'parent': '34e94e67e63a0f079d9336b3c2a52e814d138e5b3f1f614a0cfe273814ed7c0a'}),
            ('045df3e66e28eadb9be8c9156f638a4f9cfe286a696dd0641153e0d76e3e6af1', {'parent': '0c752394b855e8f15d2dc1fba6f10f4386ff6c0ab6fc6a253285bcfbfdd214f5'}),
            ('c89045c0bfe8cd62c539d0cc227eaeab7f5445002b8a711c0d5f47ec7716ad51', {'parent': '045df3e66e28eadb9be8c9156f638a4f9cfe286a696dd0641153e0d76e3e6af1'}),
            ('766dd2d9abcf5a4cc87729e938c005b0714309659b197fca61e4fd9b775b6b7b', {'parent': 'c89045c0bfe8cd62c539d0cc227eaeab7f5445002b8a711c0d5f47ec7716ad51'}),
            ('0136554511a3841a6600fbfcd551c81a9fa268b73181b6b2ef708f2b0c04c1ef', {'parent': '766dd2d9abcf5a4cc87729e938c005b0714309659b197fca61e4fd9b775b6b7b'}),
            ('2f4f35287f9436748410cba5b5911c50063715860125c1ce7941cb5e5ed6bee3', {'parent': '0136554511a3841a6600fbfcd551c81a9fa268b73181b6b2ef708f2b0c04c1ef'}),
            ('c52368e26e7b720d70bb7a0846193ff1223fdc8d97d4de979a79f8b40ec3201b', {'parent': '2f4f35287f9436748410cba5b5911c50063715860125c1ce7941cb5e5ed6bee3'}),
            ('556b4e3b80dbc6e0586faedcfccf9aadaf6dfcd0f7a245cfb801887330992f28', {'parent': 'c52368e26e7b720d70bb7a0846193ff1223fdc8d97d4de979a79f8b40ec3201b'}),
            ('91908fbd9b30e4fdaffed472fa221b01373670779dbfa9644f0e13e767c4c8ec', {'parent': '556b4e3b80dbc6e0586faedcfccf9aadaf6dfcd0f7a245cfb801887330992f28'}),
            ('3e22df6978c1e54626e8bb7a29f26ef62a2fc0a91a3180a6a577fa934038dc95', {'parent': '91908fbd9b30e4fdaffed472fa221b01373670779dbfa9644f0e13e767c4c8ec'}),
            ('10d9e7b810bff94c5d25b2432160c29c47918513ad991953dffc849ba1ff7518', {'parent': '3e22df6978c1e54626e8bb7a29f26ef62a2fc0a91a3180a6a577fa934038dc95'}),
            ('ec699ca06e4af3f5c8dcb2c68eacc406b7180043eca0ab482be46ec72461a7c1', {'parent': '10d9e7b810bff94c5d25b2432160c29c47918513ad991953dffc849ba1ff7518'}),
            ('072fa79a781c5c75172d040f6c97647348fd8a5ecc2e9481a9beb84ffefd09ba', {'parent': 'ec699ca06e4af3f5c8dcb2c68eacc406b7180043eca0ab482be46ec72461a7c1'}),
            ('ab453afd1693a9a511118510aff7020197c71be76ffafdd6edb806bf4a6346b3', {'parent': '072fa79a781c5c75172d040f6c97647348fd8a5ecc2e9481a9beb84ffefd09ba'}),
            ('4c0040c3a6522c9e80d263f7375d799af8556c42febec02d263038c8e0c2ef34', {'parent': 'ab453afd1693a9a511118510aff7020197c71be76ffafdd6edb806bf4a6346b3'}),
            ('fcd0c2f14afb225883c2490e856c2a156a1292e067207ddceae577539f229d83', {'parent': '4c0040c3a6522c9e80d263f7375d799af8556c42febec02d263038c8e0c2ef34'}),
            ('9371e36311abdb3b755b7a7cf96bded7a19e0eab5a6b194e419ed94ff01ab41f', {'parent': 'fcd0c2f14afb225883c2490e856c2a156a1292e067207ddceae577539f229d83'}),
            ('81d6602568309bf8d424b0e49b624fb1db5b00fbd9627f924fd99efa718a0735', {'parent': '9371e36311abdb3b755b7a7cf96bded7a19e0eab5a6b194e419ed94ff01ab41f'}),
            ('df631f96c362c2bf1e28723c346e63b3f08ce53667bc3f0bf43fce3b756a6914', {'parent': '81d6602568309bf8d424b0e49b624fb1db5b00fbd9627f924fd99efa718a0735'}),
            ('927091ea6458d98db3ae71ad7b94d330c782f658b015345ef457503631530876', {'parent': 'df631f96c362c2bf1e28723c346e63b3f08ce53667bc3f0bf43fce3b756a6914'}),
            ('5ab5d882784bcaf444e58392aedee94e1fb34b545ce435f75336d14f1a8b528d', {'parent': '927091ea6458d98db3ae71ad7b94d330c782f658b015345ef457503631530876'}),
            ('71ffe2a62eab626357768d5fd308b6daf8ab95e6b17aadf1dafa78462c5668da', {'parent': '5ab5d882784bcaf444e58392aedee94e1fb34b545ce435f75336d14f1a8b528d'}),
            ('a7500126890eded387ecf1a052888230b75e1968931b05f9018f4fece1cdc46e', {'parent': '71ffe2a62eab626357768d5fd308b6daf8ab95e6b17aadf1dafa78462c5668da'}),
            ('033c14f799ea4e6a1133fcb03c88c90150b83108d9bb42c415edb61d10e20ae9', {'parent': 'a7500126890eded387ecf1a052888230b75e1968931b05f9018f4fece1cdc46e'}),
            ('07cefaf30c761a3a4f09243d426ab4ac35dadcf83dba79a521257ffd1b81030a', {'parent': '033c14f799ea4e6a1133fcb03c88c90150b83108d9bb42c415edb61d10e20ae9'}),
            ('8770c17b47f7955a9b5f9a232a4f34cc62be2b2f00e2830e1459ef5c28ca33d7', {'parent': '07cefaf30c761a3a4f09243d426ab4ac35dadcf83dba79a521257ffd1b81030a'}),
            ('99a8b82393f66ccd2d57ba1efaabadaf62f5ba0a1e778ed79bd69a055ef8680a', {'parent': '8770c17b47f7955a9b5f9a232a4f34cc62be2b2f00e2830e1459ef5c28ca33d7'}),
            ('3fc782251abe2cf96c2b1f95d3e4d20396774fa6522ec0e45a6cbf8e27edc381', {'parent': '99a8b82393f66ccd2d57ba1efaabadaf62f5ba0a1e778ed79bd69a055ef8680a'}),
            ('373e0a00584542b3cf9453c023965a337489a6ee2e9624150e253d000162585e', {'parent': '3fc782251abe2cf96c2b1f95d3e4d20396774fa6522ec0e45a6cbf8e27edc381'}),
            ('06da4b2f8a21203a5fd14fa4404edd554bc6397637f063362e5a1afc12d04528', {'parent': '373e0a00584542b3cf9453c023965a337489a6ee2e9624150e253d000162585e'}),
            ('51fc1e86eeb95ed136bd1819d3801190fc81e2bd6a214ae9053561ae9c7c64a0', {'parent': '06da4b2f8a21203a5fd14fa4404edd554bc6397637f063362e5a1afc12d04528'}),
        ]
        # sort in layer id order, which is a random for our purpose
        shuffled = sorted(test_data)

        layers = [LayerOld(lid, **data) for lid, data in shuffled]
        result = LayerOld.sort(layers)
        result = [(l.layer_id, {'parent': l.parent_id}) for l in result]

        expected = test_data
        assert expected == result

        last = {'parent': None}
        for lid, pid in result:
            assert pid == last
            last = {'parent': lid}

    def test_LayerOld_sort_with_non_sortable_layers_raise_exception(self):
        # ordered in random layer order, one layer is not in the stream
        test_data = [
            ('766dd2d9abcf5a4cc87729e938c005b0714309659b197fca61e4fd9b775b6b7b', {'parent': 'c89045c0bfe8cd62c539d0cc227eaeab7f5445002b8a711c0d5f47ec7716ad51'}),
            ('c89045c0bfe8cd62c539d0cc227eaeab7f5445002b8a711c0d5f47ec7716ad51', {'parent': '045df3e66e28eadb9be8c9156f638a4f9cfe286a696dd0641153e0d76e3e6af1'}),
            ('045df3e66e28eadb9be8c9156f638a4f9cfe286a696dd0641153e0d76e3e6af1', {'parent': '0c752394b855e8f15d2dc1fba6f10f4386ff6c0ab6fc6a253285bcfbfdd214f5'}),
            ('3fc782251abe2cf96c2b1f95d3e4d20396774fa6522ec0e45a6cbf8e27edc381', {'parent': '99a8b82393f66ccd2d57ba1efaabadaf62f5ba0a1e778ed79bd69a055ef8680a'}),
            ('0c752394b855e8f15d2dc1fba6f10f4386ff6c0ab6fc6a253285bcfbfdd214f5', {'parent': '34e94e67e63a0f079d9336b3c2a52e814d138e5b3f1f614a0cfe273814ed7c0a'}),
            ('34e94e67e63a0f079d9336b3c2a52e814d138e5b3f1f614a0cfe273814ed7c0a', {'parent': '511136ea3c5a64f264b78b5433614aec563103b4d4702f3ba7d4d2698e22c158'}),
            ('511136ea3c5a64f264b78b5433614aec563103b4d4702f3ba7d4d2698e22c158', {'parent': None}),
        ]

        layers = [LayerOld(lid, **data) for lid, data in test_data]
        try:
            LayerOld.sort(layers)
        except NonSortableLayersError:
            pass


class TestDockerfile(FileBasedTesting):
    test_data_dir = os.path.join(os.path.dirname(__file__), 'data')

    def test_normalized_layer_command(self):
        # tuple of command and expected result tuples
        test_data = [
            ('#(nop) MAINTAINER The CentOS Project <cloud-ops@centos.org> - ami_creator ', ('MAINTAINER', 'The CentOS Project <cloud-ops@centos.org> - ami_creator')),
            ('#(nop) VOLUME ["/etc/elasticsearch"]', ('VOLUME', '["/etc/elasticsearch"]')),
            ('./usr/local/bin/run_rvm.sh', ('RUN', './usr/local/bin/run_rvm.sh')),
            ('', ('FROM', '')),
            (' ', ('FROM', '')),
            (None, ('FROM', '')),
            ('#(nop) ADD cacerts in /usr/java/openJDK-8-b132/jre/lib/security/cacerts', ('ADD', 'cacerts /usr/java/openJDK-8-b132/jre/lib/security/cacerts')),
            ('#(nop) CMD [/bin/sh -c supervisord -c /etc/supervisord.conf]', ('CMD', 'supervisord -c /etc/supervisord.conf')),
            ('#(nop)  ENV  CA_CERT_LOCATION=/etc/keys/ca.pem', ('ENV', 'CA_CERT_LOCATION=/etc/keys/ca.pem')),
            ('#(nop) EXPOSE map[7500/tcp:{}]', ('EXPOSE', 'map[7500/tcp:{}]')),
            ('#(nop) VOLUME ["/var/log", "/usr/local/pgsql/data"]', ('VOLUME', '["/var/log", "/usr/local/pgsql/data"]')),
            ('#(nop) WORKDIR /', ('WORKDIR', '/')),
        ]
        for layer_command, expected in test_data:
            assert expected == normalized_layer_command(layer_command)
