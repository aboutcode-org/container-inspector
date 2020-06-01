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
from unittest.case import expectedFailure

from commoncode.testcase import FileBasedTesting

from conan import image

class TestDockerFormat10(FileBasedTesting):
    test_data_dir = os.path.join(os.path.dirname(__file__), 'data')

    def test_ImageV10(self):
        test_dir = self.extract_test_tar('docker/v10_format/busybox.tgz')
        image.Image(test_dir)


@expectedFailure
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
