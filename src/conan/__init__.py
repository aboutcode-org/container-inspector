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

from __future__ import print_function
from __future__ import absolute_import
from __future__ import unicode_literals

import re

__version__ = '1.0.0'

DEFAULT_ID_LEN = 64

REPOSITORIES_FILE = 'repositories'
MANIFEST_JSON_FILE = 'manifest.json'

LAYER_VERSION_FILE = 'VERSION'
LAYER_JSON_FILE = 'json'
LAYER_TAR_FILE = 'layer.tar'

docker_version = re.compile('docker/([^\s]+)')

EMPTY_SHA256 = 'e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855'
EMPTY_DIGEST = 'sha256:'+ EMPTY_SHA256


def is_image_or_layer_id(s, layerid_len=DEFAULT_ID_LEN):
    """
    Return True if the string `s` looks like a layer ID. Checks at most layerid_len
    characters with a default to DEFAULT_ID_LEN (e.g. 64).
    """
    return re.compile(r'^[a-f0-9]{%(layerid_len)d}$' % locals()).match

