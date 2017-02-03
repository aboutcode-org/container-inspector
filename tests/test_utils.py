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

import os

from commoncode.testcase import FileBasedTesting

from conan.utils import find_shortest_prefix_length


class TestDockerUtils(FileBasedTesting):
    test_data_dir = os.path.join(os.path.dirname(__file__), 'data')

    def test_find_shortest_prefix_length(self):
        strings = [
            '766dd2d9abcf5a4cc87729e938c005b0714309659b197fca61e4fd9b775b6b7b',
            'c89045c0bfe8cd62c539d0cc227eaeab7f5445002b8a711c0d5f47ec7716ad51',
            '045df3e66e28eadb9be8c9156f638a4f9cfe286a696dd06sadasdadas41153e0d76e3e6af1',
            '3fc782251abe2cf96c2b1f95d3e4d20396774fa6522ec0e45a6cbf8e27edc381',
            '0c752394b855e8f15d2dc1fba6f10f4386ff6c0ab6fc6a253285bcfbfdd214sdaasdasdaf5',
            '34e94e67e63a0f079d9336b3c2a52e814d138e5b3f1f614a0cfe273814ed7c0a',
            '511136ea3c5a64f264b78b5433614aec563103b4d4702f3ba7d4d2698e22c158',
        ]
        assert 2 == find_shortest_prefix_length(strings)

    def test_find_shortest_prefix_length_2(self):
        strings = [
            '766dd2d9abcf5a4cc87729e938c005b0714309659b197fca61e4fd9b775b6b7b',
            '7c89045c0bfe8cd62c539d0cc227eaeab7f5445002b8a711c0d5f47ec7716ad51',
            '7045df3e66e28eadb9be8c9156f638a4f9cfe286a696dd06sadasdadas41153e0d76e3e6af1',
            '73fc782251abe2cf96c2b1f95d3e4d20396774fa6522ec0e45a6cbf8e27edc381',
            '70c752394b855e8f15d2dc1fba6f10f4386ff6c0ab6fc6a253285bcfbfdd214sdaasdasdaf5',
            '734e94e67e63a0f079d9336b3c2a52e814d138e5b3f1f614a0cfe273814ed7c0a',
            '7511136ea3c5a64f264b78b5433614aec563103b4d4702f3ba7d4d2698e22c158',
        ]
        assert 3 == find_shortest_prefix_length(strings)

