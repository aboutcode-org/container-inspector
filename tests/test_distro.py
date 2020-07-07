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

from commoncode.testcase import FileBasedTesting

from container_inspector.distro import Distro
from container_inspector.distro import parse_os_release

from utilities import check_expected


class TestDistro(FileBasedTesting):
    test_data_dir = path.join(path.dirname(__file__), 'data')

    def test_parse_os_release(self):
        test_dir = self.get_test_loc('distro/chef-os-release/os-release')
        expected_dir = self.get_test_loc('distro/chef-os-release/expected')

        for os_release in listdir(test_dir):
            test_file = path.join(test_dir, os_release)
            expected = path.join(expected_dir, os_release + '-expected.json')
            result = parse_os_release(test_file)
            check_expected(result, expected, regen=False)

    def test_distro_from_file(self):
        test_dir = self.get_test_loc('distro/chef-os-release/os-release')
        expected_dir = self.get_test_loc('distro/chef-os-release/expected-distro')

        for os_release in listdir(test_dir):
            test_file = path.join(test_dir, os_release)
            expected = path.join(expected_dir, os_release + '-expected.json')
            result = Distro.from_file(test_file).to_dict()
            check_expected(result, expected, regen=False)
