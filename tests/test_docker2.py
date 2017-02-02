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

from __future__ import absolute_import
from __future__ import print_function
from __future__ import unicode_literals

from collections import OrderedDict
import json
import os

from commoncode.testcase import FileBasedTesting

from conan.docker import Layer

regen = True

class TestLayer(FileBasedTesting):
    test_data_dir = os.path.join(os.path.dirname(__file__), 'data')

    def test_Layer(self):
        Layer()

    def test_load_layer(self):
        test_dir = self.get_test_loc('layers/layers')
        expected_dir = self.get_test_loc('layers/expected')
        for layer_id in os.listdir(test_dir):
            layer_dir = os.path.join(test_dir, layer_id)
            layer = Layer.load_layer(layer_dir)
            expected = os.path.join(expected_dir, layer_id + '.expected.json')

            if regen:
                with open(expected, 'wb') as ex:
                    ex.write(json.dumps(layer.as_dict(), indent=2))

            with open(expected) as ex:
                expected = json.loads(ex.read(), object_pairs_hook=OrderedDict)


            assert expected == layer.as_dict()
