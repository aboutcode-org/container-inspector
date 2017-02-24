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
from commoncode import fileutils

from conan.image_v11 import Image
from conan.image_v11 import Layer
from conan.image_v11 import Registry
from conan.image_v11 import Repository


def check_expected(result, expected, regen=False):
    """
    Check euquality between a result collection and an expected JSON file.
    Regen the expected file if regen is True.
    """
    if regen:
        with open(expected, 'wb') as ex:
            ex.write(json.dumps(result, indent=2))

    with open(expected) as ex:
        expected = json.loads(ex.read(), object_pairs_hook=OrderedDict)

    assert expected == result


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
            result = layer.as_dict()
            check_expected(result, expected, regen=True)


class TestImage(FileBasedTesting):
    test_data_dir = os.path.join(os.path.dirname(__file__), 'data')

    def test_Image(self):
        Image()

    def test_load_image_config(self):
        test_dir = self.get_test_loc('images/config')
        expected_dir = self.get_test_loc('images/config_expected')
        for config_file in os.listdir(test_dir):
            base_name = fileutils.file_base_name(config_file)
            config_file = os.path.join(test_dir, config_file)
            image = Image.load_image_config(config_file)
            expected = os.path.join(expected_dir, base_name + '.expected.json')
            result = image.as_dict()
            check_expected(result, expected, regen=True)


class TestRepo(FileBasedTesting):
    test_data_dir = os.path.join(os.path.dirname(__file__), 'data')

    def test_Repository(self):
        Repository()

    def test_load_manifest(self):
        test_arch = self.get_test_loc('repos/imagesv11.tar')
        test_dir = self.extract_test_tar(test_arch)
        expected = os.path.join(self.get_test_loc('repos'), 'imagesv11.tar.expected.json')
        repo = Repository()
        repo.load_manifest(test_dir)
        result = repo.as_dict()
        check_expected(result, expected, regen=True)


class TestRegistry(FileBasedTesting):
    test_data_dir = os.path.join(os.path.dirname(__file__), 'data')

    def test_Registry(self):
        Registry('assa')

    def test_populate(self):
        test_arch = self.get_test_loc('repos/imagesv11.tar')
        test_dir = self.extract_test_tar(test_arch)
        expected = os.path.join(self.get_test_loc('repos'), 'imagesv11.tar.registry.expected.json')
        repo = Registry()
        repo.populate(test_dir)
        # ignore the repo dir
        result = [r.as_dict() for r in repo.repos().values()]
        check_expected(result, expected, regen=True)
