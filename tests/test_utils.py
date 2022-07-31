#
# Copyright (c) nexB Inc. and others. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
# See http://www.apache.org/licenses/LICENSE-2.0 for the license text.
# See https://github.com/nexB/container-inspector for support or download.
# See https://aboutcode.org for more information about nexB OSS projects.
#

import os

from commoncode import fileutils
from commoncode import testcase

from container_inspector import utils

from utilities import check_expected


def check_files(target_dir, expected):
    """
    Walk test_dir.
    Check that all dirs are readable.
    Check that all files are:
     * non-special,
     * readable,
     * have a posix path that ends with one of the expected tuple paths.
    """
    result = []

    test_dir_path = fileutils.as_posixpath(target_dir)
    for top, _, files in os.walk(target_dir):
        for f in files:
            location = os.path.join(top, f)
            path = fileutils.as_posixpath(location)
            path = path.replace(test_dir_path, '').strip('/')
            result.append(path)

    expected_content = sorted(expected)
    result = sorted(result)

    assert result == expected_content


class TestUtils(testcase.FileBasedTesting):
    test_data_dir = os.path.join(os.path.dirname(__file__), 'data')

    def clean_events(self, extract_dir, events):
        """
        Return a list of events mapping cleaned from absolute paths
        """
        events_results = []
        for e in events:
            ne = e._replace(
                source=e.source.replace(extract_dir, ''),
                message=e.message.replace(self.test_data_dir, ''),
            )
            events_results.append(ne)
        events_results = sorted(events_results, key=lambda x: x.source)
        return [dict(ne._asdict()) for ne in events_results]

    def clean_paths(self, extract_dir):
        return sorted([p.replace(extract_dir, '') for p in
            fileutils.resource_iter(
                location=extract_dir,
                with_dirs=True,
                follow_symlinks=True)]
        )

    def test_extract_tree_with_colon_in_filenames(self):
        expected = (
            'colon/libc6:amd64.list',
        )
        test_dir = self.get_test_loc('utils/colon.tar.xz')
        extract_dir = self.get_temp_dir()
        events = utils.extract_tar(location=test_dir, target_dir=extract_dir)
        check_files(target_dir=extract_dir, expected=expected)
        assert not events

    def test_extract_tar_relative(self):
        expected = ()
        test_dir = self.get_test_loc('utils/tar_relative.tar')
        extract_dir = self.get_temp_dir()
        events = utils.extract_tar(location=test_dir, target_dir=extract_dir, as_events=True)
        check_files(target_dir=extract_dir, expected=expected)
        events = self.clean_events(extract_dir, events)
        expected_events = [
            {'message': '/utils/tar_relative.tar: skipping unsupported ../../another_folder/b_two_root.txt with relative path.',
             'source': '../../another_folder/b_two_root.txt',
             'type': 'warning'},
            {'message': '/utils/tar_relative.tar: skipping unsupported ../a_parent_folder.txt with relative path.',
             'source': '../a_parent_folder.txt',
             'type': 'warning'},
            {'message': '/utils/tar_relative.tar: skipping unsupported ../folder/subfolder/b_subfolder.txt with relative path.',
             'source': '../folder/subfolder/b_subfolder.txt',
             'type': 'warning'},
        ]

        assert events == expected_events

    def test_extract_tar_relative_with_whiteouts(self):
        expected = (
            '.wh..wh..opq',
            '.wh..wh..plnk',
            '.wh.foo.txt'
        )
        test_dir = self.get_test_loc('utils/tar_relative-with-whiteouts.tar')
        extract_dir = self.get_temp_dir()
        events = utils.extract_tar(location=test_dir, target_dir=extract_dir, as_events=True)
        check_files(target_dir=extract_dir, expected=expected)
        events = self.clean_events(extract_dir, events)
        expected_events = [
            {'message': '/utils/tar_relative-with-whiteouts.tar: skipping unsupported ../../another_folder/.wh..wh..opq with relative path.',
             'source': '../../another_folder/.wh..wh..opq',
             'type': 'warning'},
            {'message': '/utils/tar_relative-with-whiteouts.tar: skipping unsupported ../.wh..wh..opq with relative path.',
             'source': '../.wh..wh..opq',
             'type': 'warning'},
            {'message': '/utils/tar_relative-with-whiteouts.tar: skipping unsupported ../folder/subfolder/.wh..wh..opq with relative path.',
             'source': '../folder/subfolder/.wh..wh..opq',
             'type': 'warning'},
        ]

        assert events == expected_events

    def test_extract_tar_relative_as_strings(self):
        expected = ()
        test_dir = self.get_test_loc('utils/tar_relative.tar')
        extract_dir = self.get_temp_dir()
        events = utils.extract_tar(location=test_dir, target_dir=extract_dir, as_events=False)
        check_files(target_dir=extract_dir, expected=expected)

        events = [e.replace(self.test_data_dir, '') for e in events]
        expected_events = [
            'warning: /utils/tar_relative.tar: skipping unsupported ../a_parent_folder.txt with relative path.',
            'warning: /utils/tar_relative.tar: skipping unsupported ../../another_folder/b_two_root.txt with relative path.',
            'warning: /utils/tar_relative.tar: skipping unsupported ../folder/subfolder/b_subfolder.txt with relative path.',
            ]
        assert events == expected_events

    def test_extract_tar_absolute(self):
        expected = (
            'tmp/subdir/a.txt',
            'tmp/subdir/b.txt',
        )
        test_dir = self.get_test_loc('utils/absolute_path.tar')
        extract_dir = self.get_temp_dir()
        events = utils.extract_tar(location=test_dir, target_dir=extract_dir, as_events=True)
        check_files(target_dir=extract_dir, expected=expected)

        events = self.clean_events(extract_dir, events)
        expected_events = [
            {'message': '/utils/absolute_path.tar: absolute path name: /tmp/subdir transformed in relative path.',
             'source': '/tmp/subdir',
             'type': 'warning'},
            {'message': '/utils/absolute_path.tar: absolute path name: /tmp/subdir/a.txt transformed in relative path.',
             'source': '/tmp/subdir/a.txt',
             'type': 'warning'},
            {'message': '/utils/absolute_path.tar: absolute path name: /tmp/subdir/b.txt transformed in relative path.',
             'source': '/tmp/subdir/b.txt',
             'type': 'warning'},
        ]

        assert events == expected_events

    def test_extract_tar_not_skipping_links(self):
        test_tarball = self.get_test_loc('utils/layer_with_links.tar')
        extract_dir = self.get_temp_dir()

        events = utils.extract_tar(location=test_tarball, target_dir=extract_dir, as_events=True, skip_symlinks=False)

        results = self.clean_paths(extract_dir)
        expected_results = self.get_test_loc('utils/layer_with_links.tar.expected.json', must_exist=False)
        check_expected(results, expected_results, regen=False)

        events_results = self.clean_events(extract_dir, events)
        expected_events = self.get_test_loc('utils/layer_with_links.tar.expected-events.json', must_exist=False)
        check_expected(events_results, expected_events, regen=False)

    def test_extract_tar_skipping_links(self):
        test_tarball = self.get_test_loc('utils/layer_with_links.tar')
        extract_dir = self.get_temp_dir()

        events = utils.extract_tar(location=test_tarball, target_dir=extract_dir, as_events=True, skip_symlinks=True)

        results = self.clean_paths(extract_dir)
        expected_results = self.get_test_loc('utils/layer_with_links.tar.expected-skipping.json', must_exist=False)
        check_expected(results, expected_results, regen=False)

        events_results = self.clean_events(extract_dir, events)
        expected_events = self.get_test_loc('utils/layer_with_links.tar.expected-events-skipping.json', must_exist=False)
        check_expected(events_results, expected_events, regen=False)

    def test_extract_tar_with_symlinks(self):
        test_tarball = self.get_test_loc('utils/layer_with_links.tar')
        extract_dir = self.get_temp_dir()

        events = utils.extract_tar_with_symlinks(location=test_tarball, as_events=True, target_dir=extract_dir)

        results = self.clean_paths(extract_dir)
        expected_results = self.get_test_loc('utils/layer_with_links.tar.expected.json', must_exist=False)
        check_expected(results, expected_results, regen=False)

        events_results = self.clean_events(extract_dir, events)
        expected_events = self.get_test_loc('utils/layer_with_links.tar.expected-events.json', must_exist=False)
        check_expected(events_results, expected_events, regen=False)

    def test_extract_tar_with_broken_links_skipping_links(self):
        test_tarball = self.get_test_loc('utils/layer_with_links_missing_targets.tar')
        extract_dir = self.get_temp_dir()

        events = utils.extract_tar(location=test_tarball, target_dir=extract_dir, as_events=True, skip_symlinks=True)

        results = self.clean_paths(extract_dir)
        expected_results = self.get_test_loc('utils/layer_with_links_missing_targets.tar.expected.json', must_exist=False)
        check_expected(results, expected_results, regen=False)

        events_results = self.clean_events(extract_dir, events)
        expected_events = self.get_test_loc('utils/layer_with_links_missing_targets.tar.expected-events.json', must_exist=False)
        check_expected(events_results, expected_events, regen=False)

    def test_extract_tar_with_symlinks_with_broken_links(self):
        test_tarball = self.get_test_loc('utils/layer_with_links_missing_targets.tar')
        extract_dir = self.get_temp_dir()

        events = utils.extract_tar_with_symlinks(location=test_tarball, target_dir=extract_dir)

        results = self.clean_paths(extract_dir)
        expected_results = self.get_test_loc('utils/layer_with_links_missing_targets.tar.expected-broken.json', must_exist=False)
        check_expected(results, expected_results, regen=False)

        events_results = self.clean_events(extract_dir, events)
        expected_events = self.get_test_loc('utils/layer_with_links_missing_targets.tar.expected-events-broken.json', must_exist=False)
        check_expected(events_results, expected_events, regen=False)

