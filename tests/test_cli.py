#
# Copyright (c) nexB Inc. and others. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
# See http://www.apache.org/licenses/LICENSE-2.0 for the license text.
# See https://github.com/nexB/container-inspector for support or download.
# See https://aboutcode.org for more information about nexB OSS projects.
#

import os
import json

from commoncode.testcase import FileBasedTesting

from container_inspector import cli
from commoncode import fileutils

from utilities import check_expected


def clean_images_data(images):
    """
    Clean an Image.to_dict() for testing
    """
    for i in images:
        i['extracted_location'] = None
        i['archive_location'] = None
        for l in i['layers']:
            l['extracted_location'] = None
            l['archive_location'] = None
    return images


class TestContainerInspectorCli(FileBasedTesting):
    test_data_dir = os.path.join(os.path.dirname(__file__), 'data')

    def test_container_inspector_single_layer_from_dir(self):
        test_dir = self.extract_test_tar('cli/hello-world.tar')
        expected = self.get_test_loc('cli/hello-world.tar-inventory-from-dir-expected.json')
        out = cli._container_inspector(image_path=test_dir)
        result = clean_images_data(json.loads(out))
        check_expected(result, expected, regen=False)

    def test_container_inspector_single_layer_from_tarball(self):
        test_dir = self.get_test_loc('cli/hello-world.tar')
        expected = self.get_test_loc('cli/hello-world.tar-inventory-from-tarball-expected.json')
        out = cli._container_inspector(image_path=test_dir)
        result = clean_images_data(json.loads(out))
        check_expected(result, expected, regen=False)

    def test_container_inspector_multiple_layers_from_tarball(self):
        test_dir = self.get_test_loc('cli/she-image_from_scratch-1.0.tar')
        expected = self.get_test_loc('cli/she-image_from_scratch-1.0.tar-inventory-from-tarball-expected.json')
        out = cli._container_inspector(image_path=test_dir)
        result = clean_images_data(json.loads(out))
        check_expected(result, expected, regen=False)

    def test_squash_single_layer(self):
        test_dir = self.extract_test_tar('cli/hello-world.tar')
        target_dir = self.get_temp_dir()

        cli._container_inspector_squash(
            image_path=test_dir,
            extract_directory=target_dir)

        results = sorted([p.replace(target_dir, '')
            for p in fileutils.resource_iter(target_dir)])
        expected = ['/hello']
        assert expected == results

    def test_squash_multiple_layers(self):
        test_dir = self.extract_test_tar('cli/she-image_from_scratch-1.0.tar')
        target_dir = self.get_temp_dir()

        cli._container_inspector_squash(
            image_path=test_dir,
            extract_directory=target_dir,
        )

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
