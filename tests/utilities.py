#
# Copyright (c) nexB Inc. and others. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
# See http://www.apache.org/licenses/LICENSE-2.0 for the license text.
# See https://github.com/nexB/container-inspector for support or download.
# See https://aboutcode.org for more information about nexB OSS projects.
#

import json
import os


def check_expected(result, expected, regen=False):
    """
    Check equality between a result collection and an expected JSON file.
    Regen the expected file if regen is True.
    """
    if regen:
        with open(expected, 'w') as ex:
            ex.write(json.dumps(result, indent=2))

    with open(expected) as ex:
        expected = json.loads(ex.read())

    assert result == expected


def clean_image(image):
    """
    Clean `image` data for test purpose
    """
    image.extracted_location = ''
    image.archive_location = ''
    for layer in image.layers:
        layer.extracted_location = os.path.basename(layer.extracted_location or '')
        layer.archive_location = os.path.basename(layer.archive_location or '')
    return image
