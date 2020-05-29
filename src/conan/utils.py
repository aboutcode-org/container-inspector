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

from collections import OrderedDict
from collections import Mapping
from copy import deepcopy
import json
import logging
import os
from os.path import isdir

from commoncode.hash import sha256


logger = logging.getLogger(__name__)
# un-comment these lines to enable logging
# logging.basicConfig(level=logging.DEBUG, stream=sys.stdout)
# logger.setLevel(logging.DEBUG)



def load_json(location):
    """
    Return the data loaded from a JSON file at `location`.
    Ensure that the mapping are ordered.
    """
    with open(location) as loc:
        data = json.loads(loc.read(), object_pairs_hook=OrderedDict)
    return data


def listdir(location):
    """
    Return a list of files and directories in the location directory or an empty
    list. Ignore extracted directed directories.
    """
    if not isdir(location):
        return []
    import extractcode
    return [f for f in os.listdir(location) if not f.endswith(extractcode.EXTRACT_SUFFIX)]


def find_shortest_prefix_length(strings):
    """
    Given a list of strings (typically a list of image or layer ids), return the
    smallest length that could be used to truncate these strings such that they still
    would be uniquely identified by this truncated prefix. Used to shorten long hash-
    like Layer Ids when analyzed together to make things more human friendly.
    """
    uniques = set(strings)
    shortest_len = max(len(s) for s in uniques)
    unique_count = len(uniques)
    # iterate the range of possible length backwards
    # start=shortest_len - 1, stop=0, step=-1
    for length in range(shortest_len - 1, 0, -1):
        truncated = set(s[:length] for s in uniques)
        if len(truncated) == unique_count:
            shortest_len = length
            continue
        else:
            break
    return shortest_len


def get_command(cmd):
    """
    Clean the command for this layer.
    """
    # FIXME: this need to be cleaned further
    return cmd and ' '.join([c for c in cmd if not c.startswith(('/bin/sh', '-c',))]) or ''


def sha256_digest(location):
    """
    Return an algorithm-prefixed checksum for the file content at location.
    """
    return location and ('sha256:' + unicode(sha256(location)))


def as_bare_id(string):
    """
    Return an id stripped from its leading checksum algorithm prefix if present.
    """
    if not string:
        return string
    if string.startswith('sha256:'):
        _, _, string = string.partition('sha256:')
    return string


# Common empty elements (used to distinguish these from a boolean)
EMPTIES = (None, {}, [], set(), tuple(), '', OrderedDict(), 0,)


def merge_update_mappings(map1, map2, mapping=dict):
    """
    Return a new mapping and a list of warnings merging two mappings such that:
     - identical values are left unchanged
     - when values differ:
      - if one of the two values is None or empty or an empty stripped string, keep
        the non-empty value.
      - otherwise the map1 value is kept and a warning message is added to the warnings
        that the values differ
    This procedure is applied recursively.

    `mapping` is the mapping class to retrun either a dict or OrderedDict.

    For example:
    >>> map1 = {
    ...   '1': {
    ...     'first': {1:2, 2:3},
    ...     'second': 'third',
    ...     'third': 'one',
    ...     'fourth': None,
    ...     'sixth': False,
    ...     'seventh': False,
    ...   },
    ...   '2': [1, 2, 3]
    ... }
    >>> map2 = {
    ...   '1': {
    ...     'first': {1:3, 3:4},
    ...     'second': 'third',
    ...     'third': 'two',
    ...     'fourth': 'some',
    ...     'fifth': None,
    ...     'seventh': True,
    ...   },
    ...   '2': [1, 2, 3, 4]
    ... }
    >>> res, warn = merge_update_mappings(map1, map2)
    >>> expected = {
    ...   '1': {
    ...     'first': {1: 2, 2: 3, 3: 4},
    ...     'second': 'third',
    ...     'third': 'one',
    ...     'fourth': 'some',
    ...     'fifth': None,
    ...     'sixth': False,
    ...     'seventh': True,
    ...   },
    ...   '2': [1, 2, 3, 4]}
    >>> assert expected == dict(res)
    >>> ex_warn = [
    ...   'WARNING: Values differ for "third": keeping first value: "one" != "two".',
    ...   'WARNING: Values differ for "1": keeping first value: "2" != "3".'
    ... ]
    >>> assert ex_warn == warn
    """
    warnings = []

    if map1 and not map2:
        return mapping(map1), warnings

    if map2 and not map1:
        return mapping(map2), warnings

    keys = map1.keys()
    keys.extend(k2 for k2 in map2.keys() if k2 not in keys)
    new_map = mapping()
    for key in keys:
        value1 = deepcopy(map1.get(key))
        value2 = deepcopy(map2.get(key))

        # strip strings
        if isinstance(value1, str):
            value1 = value1.strip()
        if isinstance(value2, str):
            value2 = value2.strip()

        if value1 == value2:
            new_map[key] = value1

        elif isinstance(value1, bool) or isinstance(value2, bool):
            new_map[key] = bool(value1 or value2)

        elif value1 and value2 in EMPTIES:
            new_map[key] = value1

        elif value2 and value1 in EMPTIES:
            new_map[key] = value2

        elif isinstance(value1, Mapping):
            if not value2:
                value2 = {}
            assert isinstance(value2, Mapping)
            # recurse to merge v1 and v2
            new_value, vwarns = merge_update_mappings(value1, value2, mapping)
            warnings.extend(vwarns)
            new_map[key] = new_value

        elif isinstance(value1, (list, tuple, set)):
            assert isinstance(value2, (list, tuple, set))
            # append new v2 items to v1
            new_value = value1 + [v for v in value2 if v not in value1]
            new_map[key] = new_value

        elif value1 != value2:
            new_map[key] = value1
            wmessage = 'WARNING: Values differ for "%(key)s": keeping first value: "%(value1)s" != "%(value2)s".' % locals()
            warnings.append(wmessage)

    return new_map, warnings

