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

from os import path

from commoncode.testcase import FileBasedTesting

from container_inspector.image import Image
from container_inspector.image import flatten_images_data

from utilities import check_expected
from utilities import clean_image


class TestImages(FileBasedTesting):
    test_data_dir = path.join(path.dirname(__file__), 'data')

    def test_Image(self):
        try:
            Image()
            self.fail('Exception not caught')
        except TypeError as e:
            assert str(e) == 'Image.extracted_location is a required argument'

    def test_Image_with_dir(self):
        test_dir = self.get_temp_dir()
        Image(extracted_location=test_dir)

    def test_Image_get_images_from_tarball(self):
        test_tarball = self.get_test_loc('repos/imagesv11.tar')
        extract_dir = self.get_temp_dir()
        expected = path.join(
            self.get_test_loc('repos'),
            'imagesv11.tar.expected.json',
        )

        images = Image.get_images_from_tarball(
            archive_location=test_tarball,
            extracted_location=extract_dir,
            verify=False,
        )
        result = [clean_image(i).to_dict() for i in images]
        check_expected(result, expected, regen=False)

    def test_Image_get_images_from_dir(self):
        test_tarball = self.get_test_loc('repos/imagesv11.tar')
        test_dir = self.extract_test_tar(test_tarball)
        expected = path.join(
            self.get_test_loc('repos'),
            'imagesv11.tar.expected.json',
        )
        images = Image.get_images_from_dir(
            extracted_location=test_dir,
            archive_location=test_tarball,
        )
        result = [clean_image(i).to_dict() for i in images]
        check_expected(result, expected, regen=False)

    def test_Image_get_images_from_dir_from_hello_world(self):
        test_arch = self.get_test_loc('repos/hello-world.tar')
        test_dir = self.extract_test_tar(test_arch)
        expected = path.join(
            self.get_test_loc('repos'),
            'hello-world.tar.registry.expected.json',
        )
        images = Image.get_images_from_dir(test_dir)
        result = [clean_image(i).to_dict() for i in images]
        check_expected(result, expected, regen=False)

    def test_Image_get_images_from_dir_then_flatten_images_data(self):
        test_arch = self.get_test_loc('repos/hello-world.tar')
        test_dir = self.extract_test_tar(test_arch)
        expected = path.join(
            self.get_test_loc('repos'),
            'hello-world.tar.flatten.expected.json',
        )
        images = [clean_image(i) for i in Image.get_images_from_dir(test_dir)]
        result = list(flatten_images_data(images))
        check_expected(result, expected, regen=False)

    def test_Image_get_images_from_dir_with_direct_at_root_layerid_dot_tar_tarball(self):
        test_arch = self.get_test_loc('repos/imagesv11_with_tar_at_root.tar')
        test_dir = self.extract_test_tar(test_arch)
        expected = path.join(
            self.get_test_loc('repos'),
            'imagesv11_with_tar_at_root.tar.registry.expected.json',
        )
        images = Image.get_images_from_dir(test_dir, verify=False)
        result = [clean_image(i).to_dict() for i in images]
        check_expected(result, expected, regen=False)

    def test_Image_get_images_from_dir_with_verify(self):
        test_arch = self.get_test_loc('repos/hello-world.tar')
        test_dir = self.extract_test_tar(test_arch)
        Image.get_images_from_dir(test_dir, verify=True)

    def test_Image_get_images_from_dir_with_anotations(self):
        test_arch = self.get_test_loc('repos/images.tar.gz')
        test_dir = self.extract_test_tar(test_arch)
        expected = path.join(self.get_test_loc('repos'), 'images.tar.gz.expected.json')
        images = Image.get_images_from_dir(test_dir, verify=False)
        result = [clean_image(i).to_dict() for i in images]
        check_expected(result, expected, regen=False)

    def test_Image_get_images_from_dir_with_verify_fails_if_invalid_checksum(self):
        test_arch = self.get_test_loc('repos/images.tar.gz')
        test_dir = self.extract_test_tar(test_arch)
        try:
            Image.get_images_from_dir(test_dir, verify=True)
            self.fail('Exception not raised')
        except Exception as e:
            assert str(e).startswith('Layer archive: SHA256:')

    def test_Image_find_format(self):
        test_arch = self.get_test_loc('image/she-image_from_scratch-1.0.tar')
        test_dir = self.extract_test_tar(test_arch)
        assert Image.find_format(test_dir) == 'docker'
