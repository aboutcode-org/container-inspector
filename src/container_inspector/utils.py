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
import traceback
from typing import NamedTuple

from commoncode import fileutils

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


class ExtractEvent(NamedTuple):
    """
    Represent an extraction event of interest. These are returned when running
    extract_tar
    """

    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    # type of event: one of error, warning or info
    type: str
    # source path in the archive
    source: str
    # even message
    message: str

    def to_string(self):
        return f"{self.type}: {self.message}"


def is_relative_path(path):
    """
    Return True if ``path`` is a relative path.
    >>> is_relative_path('.wh..wh..opq')
    False
    >>> is_relative_path('.wh/../wh..opq')
    True
    >>> is_relative_path('..foor')
    False
    >>> is_relative_path('../foor')
    True
    >>> is_relative_path('.//.foor//..')
    True
    """
    return any(name == '..' for name in path.split('/'))


def extract_tar(location, target_dir, as_events=False, skip_symlinks=True, trace=TRACE):
    """
    Extract a tar archive at ``location`` in the ``target_dir`` directory.
    Return a list of ExtractEvent is ``as_events`` is True, or a list of message
    strings otherwise. This list can be empty. Skip symlinks and hardlinks if
    skip_symlinks is True.

    Ignore special device files.
    Do not preserve the permissions and owners.
    """
    import tarfile
    if trace:
        logger.debug(f'_extract_tar: {location} to {target_dir} skip_symlinks: {skip_symlinks}')

    fileutils.create_dir(target_dir)

    events = []
    with tarfile.open(location) as tarball:

        for tarinfo in tarball:
            if trace:
                logger.debug(f'extract_tar: {location!r}: {tarinfo}')

            if tarinfo.isdev() or tarinfo.ischr() or tarinfo.isblk() or tarinfo.isfifo() or tarinfo.sparse:
                msg = f'skipping unsupported {tarinfo.name} file type: block, chr, dev or sparse file'
                events.append(ExtractEvent(type=ExtractEvent.INFO, source=tarinfo.name, message=msg))
                if trace:
                    logger.debug(f'extract_tar: {msg}')
                continue

            if is_relative_path(tarinfo.name):
                msg = f'{location}: skipping unsupported {tarinfo.name} with relative path.'
                events.append(ExtractEvent(type=ExtractEvent.WARNING, source=tarinfo.name, message=msg))
                if trace:
                    logger.debug(f'extract_tar: {msg}')
                continue

            if skip_symlinks and (tarinfo.islnk() or tarinfo.issym()):
                msg = f'{location}: skipping link with skip_symlinks: {skip_symlinks}: {tarinfo.name} -> {tarinfo.linkname}'
                if trace:
                    logger.debug(f'extract_tar: {msg}')
                continue

            if tarinfo.name.startswith('/'):
                msg = f'{location}: absolute path name: {tarinfo.name} transformed in relative path.'
                events.append(ExtractEvent(type=ExtractEvent.WARNING, source=tarinfo.name, message=msg))
                tarinfo.name = tarinfo.name.lstrip('/')
                if trace:
                    logger.debug(f'extract_tar: {msg}')

            # finally extract proper
            tarinfo.mode = 0o755

            try:
                tarball.extract(member=tarinfo, path=target_dir, set_attrs=False,)
            except Exception:
                msg = f'{location}: failed to extract: {tarinfo.name}: {traceback.format_exc()}'
                events.append(ExtractEvent(type=ExtractEvent.ERROR, source=tarinfo.name, message=msg))
                if trace:
                    logger.debug(f'extract_tar: {msg}')
    if not as_events:
        events = [e.to_string() for e in events]
    return events


def extract_tar_with_symlinks(location, target_dir, as_events=False):
    return extract_tar(location=location, target_dir=target_dir, as_events=as_events, skip_symlinks=False,)


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
