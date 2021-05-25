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

import os

from commoncode.testcase import FileBasedTesting
from commoncode.fileutils import resource_iter

from container_inspector.distro import Distro
from container_inspector.distro import parse_os_release

from utilities import check_expected


class TestDistro(FileBasedTesting):
    test_data_dir = os.path.join(os.path.dirname(__file__), 'data')

    def test_parse_os_release(self):
        test_dir = self.get_test_loc('distro/os-release')

        for test_file in resource_iter(test_dir, with_dirs=False):
            if test_file.endswith('expected.json'):
                continue
            expected = test_file + '-expected.json'
            result = parse_os_release(test_file)
            check_expected(result, expected, regen=False)

    def test_distro_from_os_release_file(self):
        test_dir = self.get_test_loc('distro/os-release')

        for test_file in resource_iter(test_dir, with_dirs=False):
            if test_file.endswith('-expected.json'):
                continue
            expected = test_file + '-distro-expected.json'
            result = Distro.from_os_release_file(test_file).to_dict()
            check_expected(result, expected, regen=False)
