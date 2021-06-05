#
# Copyright (c) nexB Inc. and others. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
# See http://www.apache.org/licenses/LICENSE-2.0 for the license text.
# See https://github.com/nexB/container-inspector for support or download.
# See https://aboutcode.org for more information about nexB OSS projects.
#

import json
import logging
import hashlib
import os

from commoncode import fileutils

from extractcode.extract import extract_file

TRACE = False
logger = logging.getLogger(__name__)
if TRACE:
    import sys
    logging.basicConfig(level=logging.DEBUG, stream=sys.stdout)
    logger.setLevel(logging.DEBUG)


def load_json(location):
    """
    Return the data loaded from a JSON file at `location`.
    Ensure that the mapping are ordered.
    """
    with open(location) as loc:
        data = json.load(loc)
    return data


def get_command(cmds):
    """
    Clean the `cmds` list of command strings as found in a Docker image layer
    history.
    """
    # FIXME: this need to be cleaned further
    cmds = cmds or []
    cmds = [c for c in cmds if not c.startswith(('/bin/sh', '-c',))]
    return ' '.join(cmds)


def sha256_digest(location):
    """
    Return a SHA256 checksum for the file content at location.
    """
    if location and os.path.exists(location):
        with open(location, 'rb') as loc:
            sha256 = hashlib.sha256(loc.read())
        return str(sha256.hexdigest())


def as_bare_id(string):
    """
    Return an id stripped from its leading checksum algorithm prefix if present.
    """
    if not string:
        return string
    if string.startswith('sha256:'):
        _, _, string = string.partition('sha256:')
    return string


def get_labels(config, container_config):
    """
    Return a sorted mapping of unique labels from the merged config and
    container_config mappings
    """
    labels = {}

    config = lower_keys(config)
    config_labels = config.get('labels', {}) or {}
    labels.update(config_labels.items())

    container_config = lower_keys(container_config)
    container_labels = container_config.get('labels', {}) or {}
    labels.update(container_labels.items())
    return dict(sorted(labels.items()))


def extract_tar(location, target_dir):
    """
    Extract a tar archive at `location` in the `target_dir` directory.
    Ignore special device files and symlinks and hardlinks.
    Do not preserve the permissions and owners.
    Raise an Exception on error.
    """
    errors = []
    fileutils.create_dir(target_dir)
    for event in extract_file(location, target_dir):
        if event.done:
            errors.extend(event.errors)

    if errors:
        raise Exception(f'Failed to extract: {location} to: {target_dir}', *errors)


def extract_tar_keeping_symlinks(location, target_dir):
    """
    Extract a tar archive at `location` in the `target_dir` directory.
    Ignore special device files. Keep symlinks and hardlinks
    Do not preserve the permissions and owners.
    Raise exceptions on possible problematic relative paths.
    """
    import tarfile
    if TRACE: logger.debug(f'extract_tar_keeping_symlinks: {location} to {target_dir}')

    fileutils.create_dir(target_dir)


    with tarfile.open(location) as tarball:
        # never extract character device, block and fifo files:
        # we extract dirs, files and links only
        for tinfo in tarball:
            if tinfo.isdev():
                continue
            if TRACE: logger.debug(f'extract_tar_keeping_symlinks: {tinfo}')
            tarball.extract(
                member=tinfo,
                path=target_dir,
                set_attrs=False,
            )


def lower_keys(mapping):
    """
    Return a new ``mapping`` modified such that all keys are lowercased strings.
    Fails with an Exception if a key is not a string-like obect.
    Perform this operation recursively on nested mapping and lists.

    For example::
    >>> lower_keys({'baZ': 'Amd64', 'Foo': {'Bar': {'ABC': 'bAr'}}})
    {'baz': 'Amd64', 'foo': {'bar': {'abc': 'bAr'}}}
    """
    new_mapping = {}
    for key, value in mapping.items():
        if isinstance(value, dict):
            value = lower_keys(value)
        new_mapping[key.lower()] = value
    return new_mapping
