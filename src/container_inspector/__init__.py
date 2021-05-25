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

