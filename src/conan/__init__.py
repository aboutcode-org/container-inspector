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

import re

__version__ = '1.0.0'

DEFAULT_LAYER_ID_LEN = 64

REPOSITORIES_JSON_FILE_V11 = 'repositories'
MANIFEST_JSON_FILE_V10 = 'manifest.json'

LAYER_TAR_FILE = 'layer.tar'
LAYER_JSON_FILE = 'json'
LAYER_VERSION_FILE = 'VERSION'
LAYER_FILES = set([LAYER_TAR_FILE, LAYER_JSON_FILE, LAYER_VERSION_FILE])


docker_version = re.compile('docker/([^\s]+)')



class InconsistentLayersOderingError(Exception):
    pass


class NonSortableLayersError(Exception):
    pass

