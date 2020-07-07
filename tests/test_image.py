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

from __future__ import absolute_import
from __future__ import print_function
from __future__ import unicode_literals

from os import path
from os import listdir
from unittest.case import expectedFailure

from commoncode.testcase import FileBasedTesting

from container_inspector.image import Image
from container_inspector.image import Layer
from container_inspector.image import flatten_images

from utilities import check_expected
from utilities import clean_image
from utilities import clean_layer


class TestLegacyLayer(FileBasedTesting):
    test_data_dir = path.join(path.dirname(__file__), 'data')

    def test_Layer(self):
        Layer()

    def test_load_layer(self):
        test_dir = self.get_test_loc('layers/layers')
        expected_dir = self.get_test_loc('layers/expected')
        for layer_id in listdir(test_dir):
            layer_dir = path.join(test_dir, layer_id)
            layer = Layer.from_layer_dir(layer_dir)
            expected = path.join(expected_dir, layer_id + '.expected.json')
            result = clean_layer(layer).to_dict()
            check_expected(result, expected, regen=False)


class TestImages(FileBasedTesting):
    test_data_dir = path.join(path.dirname(__file__), 'data')

    def test_Image(self):
        Image()

    def test_from_tarball(self):
        test_tarball = self.get_test_loc('repos/imagesv11.tar')
        extract_dir = self.get_temp_dir()
        expected = path.join(self.get_test_loc('repos'), 'imagesv11.tar.expected.json')
        result = [clean_image(i).to_dict()
            for i in Image.get_images_from_tarball(test_tarball, extract_dir, force_extract=True)]
        check_expected(result, expected, regen=False)

    def test_from_dir(self):
        test_tarball = self.get_test_loc('repos/imagesv11.tar')
        test_dir = self.extract_test_tar(test_tarball)
        expected = path.join(self.get_test_loc('repos'), 'imagesv11.tar.expected.json')
        result = [clean_image(i).to_dict()
            for i in Image.get_images_from_dir(test_dir)]
        check_expected(result, expected, regen=False)

    def test_from_hello_world(self):
        test_arch = self.get_test_loc('repos/hello-world.tar')
        test_dir = self.extract_test_tar(test_arch)
        expected = path.join(self.get_test_loc('repos'), 'hello-world.tar.registry.expected.json')
        result = [clean_image(i).to_dict()
            for i in Image.get_images_from_dir(test_dir)]
        check_expected(result, expected, regen=False)

    def test_flatten_images(self):
        test_arch = self.get_test_loc('repos/hello-world.tar')
        test_dir = self.extract_test_tar(test_arch)
        expected = path.join(self.get_test_loc('repos'), 'hello-world.tar.flatten.expected.json')
        images = [clean_image(i) for i in Image.get_images_from_dir(test_dir)]
        result = list(flatten_images(images))
        check_expected(result, expected, regen=False)

    # rare and not yet supported
    @expectedFailure
    def test_images_with_direct_at_root_layerid_dot_tar_tarball(self):
        test_arch = self.get_test_loc('repos/imagesv11_with_tar_at_root.tar')
        test_dir = self.extract_test_tar(test_arch)
        expected = path.join(self.get_test_loc('repos'), 'imagesv11_with_tar_at_root.tar.registry.expected.json')
        result = [clean_image(i).to_dict()
            for i in Image.get_images_from_dir(test_dir)]
        check_expected(result, expected, regen=False)
