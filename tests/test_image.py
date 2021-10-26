#
# Copyright (c) nexB Inc. and others. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
# See http://www.apache.org/licenses/LICENSE-2.0 for the license text.
# See https://github.com/nexB/container-inspector for support or download.
# See https://aboutcode.org for more information about nexB OSS projects.
#

import os

from commoncode.testcase import FileBasedTesting

from container_inspector.image import Image
from container_inspector.image import flatten_images_data

from utilities import check_expected


class TestImages(FileBasedTesting):
    test_data_dir = os.path.join(os.path.dirname(__file__), 'data')

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
        expected = os.path.join(
            self.get_test_loc('repos'),
            'imagesv11.tar.expected.json',
        )

        images = Image.get_images_from_tarball(
            archive_location=test_tarball,
            extracted_location=extract_dir,
            verify=False,
        )
        result = [i.to_dict(layer_path_segments=2, _test=True) for i in images]
        check_expected(result, expected, regen=False)

    def test_windows_container_Image_get_images_from_tarball(self):
        test_tarball = self.get_test_loc('image/windows-mini-image.tar.gz')
        extract_dir = self.get_temp_dir()
        image = Image.get_images_from_tarball(
            archive_location=test_tarball,
            extracted_location=extract_dir,
            verify=False,
        )[0]

        image.extract_layers(extracted_location=extract_dir)
        image.get_and_set_distro()
        result = image.to_dict(layer_path_segments=1, _test=True)
        expected = self.get_test_loc(
            'image/windows-mini-image.tar.gz.expected.json',
            must_exist=False,
        )

        check_expected(result, expected, regen=False)

    def test_Image_get_images_from_dir(self):
        test_tarball = self.get_test_loc('repos/imagesv11.tar')
        test_dir = self.extract_test_tar(test_tarball)
        expected = os.path.join(
            self.get_test_loc('repos'),
            'imagesv11.tar.expected.json',
        )
        images = Image.get_images_from_dir(
            extracted_location=test_dir,
            archive_location=test_tarball,
        )
        result = [i.to_dict(layer_path_segments=2, _test=True) for i in images]
        check_expected(result, expected, regen=False)

    def test_Image_get_images_from_dir_from_hello_world(self):
        test_arch = self.get_test_loc('repos/hello-world.tar')
        test_dir = self.extract_test_tar(test_arch)
        expected = os.path.join(
            self.get_test_loc('repos'),
            'hello-world.tar.registry.expected.json',
        )
        images = Image.get_images_from_dir(test_dir)
        result = [i.to_dict(layer_path_segments=2, _test=True) for i in images]
        check_expected(result, expected, regen=False)

    def test_Image_get_images_from_dir_then_flatten_images_data(self):
        test_arch = self.get_test_loc('repos/hello-world.tar')
        test_dir = self.extract_test_tar(test_arch)
        expected = os.path.join(
            self.get_test_loc('repos'),
            'hello-world.tar.flatten.expected.json',
        )
        images = list(Image.get_images_from_dir(test_dir))
        result = list(flatten_images_data(images, layer_path_segments=2, _test=True))
        check_expected(result, expected, regen=False)

    def test_Image_get_images_from_dir_with_direct_at_root_layerid_dot_tar_tarball(self):
        test_arch = self.get_test_loc('repos/imagesv11_with_tar_at_root.tar')
        test_dir = self.extract_test_tar(test_arch)
        expected = os.path.join(
            self.get_test_loc('repos'),
            'imagesv11_with_tar_at_root.tar.registry.expected.json',
        )
        images = Image.get_images_from_dir(test_dir, verify=False)
        result = [i.to_dict(layer_path_segments=2, _test=True) for i in images]
        check_expected(result, expected, regen=False)

    def test_Image_get_images_from_dir_with_verify(self):
        test_arch = self.get_test_loc('repos/hello-world.tar')
        test_dir = self.extract_test_tar(test_arch)
        Image.get_images_from_dir(test_dir, verify=True)

    def test_Image_get_images_from_dir_with_anotations(self):
        test_arch = self.get_test_loc('repos/images.tar.gz')
        test_dir = self.extract_test_tar(test_arch)
        expected = os.path.join(self.get_test_loc('repos'), 'images.tar.gz.expected.json')
        images = Image.get_images_from_dir(test_dir, verify=False)
        result = [i.to_dict(layer_path_segments=2, _test=True) for i in images]
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

    def test_Image_find_format_finds_Docker_images_without_repositories(self):
        test_arch = self.get_test_loc('image/mini-image_from_scratch-2.0.tar')
        test_dir = self.extract_test_tar(test_arch)
        assert Image.find_format(test_dir) == 'docker'

    def test_Image_to_dict_can_report_image_trimmed_layer_paths_or_not(self):
        test_image = self.get_test_loc('image/mini-image_from_scratch-2.0.tar')
        extract_dir = self.get_temp_dir()
        images = Image.get_images_from_tarball(
            archive_location=test_image,
            extracted_location=extract_dir,
            verify=False,
        )
        expected1 = self.get_test_loc(
            'image/mini-image_from_scratch-2.0.tar-relative-expected.json',
            must_exist=False,
        )
        result = [i.to_dict(layer_path_segments=2, _test=True) for i in images]
        check_expected(result, expected1, regen=False)
