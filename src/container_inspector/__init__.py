#
# Copyright (c) nexB Inc. and others. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
# See http://www.apache.org/licenses/LICENSE-2.0 for the license text.
# See https://github.com/nexB/container-inspector for support or download.
# See https://aboutcode.org for more information about nexB OSS projects.
#

import re

MANIFEST_JSON_FILE = 'manifest.json'

LAYER_TAR_FILE = 'layer.tar'

EMPTY_SHA256 = 'e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855'
EMPTY_DIGEST = 'sha256:' + EMPTY_SHA256


def is_image_or_layer_id(s):
    """
    Return True if the string `s` looks like a layer ID e.g. a SHA256-like id.
    """
    return re(r'^[a-f0-9]{64}$', re.IGNORECASE).match(s)

