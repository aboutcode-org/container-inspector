#
# Copyright (c) nexB Inc. and others. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
# See http://www.apache.org/licenses/LICENSE-2.0 for the license text.
# See https://github.com/nexB/container-inspector for support or download.
# See https://aboutcode.org for more information about nexB OSS projects.
#

import logging
import os
import tempfile

from commoncode.fileutils import copytree
from commoncode.fileutils import delete
from commoncode.paths import split

TRACE = False
logger = logging.getLogger(__name__)
if TRACE:
    import sys
    logging.basicConfig(level=logging.DEBUG, stream=sys.stdout)
    logger.setLevel(logging.DEBUG)

"""
Utilities to handle image and layer archives and recreate proper rootfs
from these archives.
"""


class InconsistentLayersError(Exception):
    pass


def rebuild_rootfs(img, target_dir):
    """
    Extract and merge or "squash" all layers of the `image` Image in a single
    rootfs in `target_dir`. Extraction is done in sequence from the bottom (root
    or initial) layer to the top (or latest) layer and the "whiteouts"
    unionfs/overlayfs procedure is applied at each step as per the OCI spec:
    https://github.com/opencontainers/image-spec/blob/master/layer.md#whiteouts

    Return a list of deleted "whiteout" files.
    Raise an Exception on errrors.

    The extraction process consists of these steps:
     - extract the layer in a temp directory
     - find whiteouts in that layer temp dir
     - remove files/directories corresponding to these whiteouts in the target directory
     - remove whiteouts special marker files or dirs in the tempdirectory
     - move layer to the target directory, overwriting existing files

    See also some related implementations and links:
    https://github.com/moby/moby/blob/d1f470946/pkg/archive/whiteouts.go
    https://github.com/virt-manager/virt-bootstrap/blob/8a7e752d/src/virtBootstrap/whiteout.py
    https://github.com/goldmann/docker-squash

    https://github.com/moby/moby/blob/master/image/spec/v1.md
    https://github.com/moby/moby/blob/master/image/spec/v1.1.md
    https://github.com/moby/moby/blob/master/image/spec/v1.2.md
    """

    assert os.path.isdir(target_dir)

    # log  deletions
    deletions = []

    for layer_num, layer in enumerate(img.layers):
        if TRACE: logger.debug(
            f'Extracting layer {layer_num} - {layer.layer_id} '
            f'tarball: {layer.archive_location}'
        )

        # 1. extract a layer to temp.
        # Note that we are not preserving any special file and any file permission
        extracted_loc = tempfile.mkdtemp('container_inspector-docker')
        layer.extract(extracted_location=extracted_loc)
        if TRACE: logger.debug(f'  Extracted layer to: {extracted_loc}')

        # 2. find whiteouts in that layer.
        whiteouts = list(find_whiteouts(extracted_loc))
        if TRACE: logger.debug('  Merging extracted layers and applying unionfs whiteouts')
        if TRACE: logger.debug('  Whiteouts:\n' + '     \n'.join(map(repr, whiteouts)))

        # 3. remove whiteouts in the previous layer stack (e.g. the WIP rootfs)
        for whiteout_marker_loc, whiteable_path in whiteouts:
            if TRACE: logger.debug(f'    Deleting dir or file with whiteout marker: {whiteout_marker_loc}')
            whiteable_loc = os.path.join(target_dir, whiteable_path)
            delete(whiteable_loc)
            # also delete the whiteout marker file
            delete(whiteout_marker_loc)
            deletions.append(whiteable_loc)

        # 4. finall copy/overwrite the extracted layer over the WIP rootfs
        if TRACE: logger.debug(f'  Moving extracted layer from: {extracted_loc} to: {target_dir}')
        copytree(extracted_loc, target_dir)
        if TRACE: logger.debug(f'  Moved layer to: {target_dir}')
        delete(extracted_loc)

    return deletions


WHITEOUT_EXPLICIT_PREFIX = '.wh.'
WHITEOUT_OPAQUE_PREFIX = '.wh..wh.opq'


def is_whiteout_marker(path):
    """
    Return True if the ``path`` is a whiteout marker file.

    For example::
    >>> is_whiteout_marker('.wh.somepath')
    True
    >>> is_whiteout_marker('.wh..wh.opq')
    True
    >>> is_whiteout_marker('somepath.wh.')
    False
    >>> is_whiteout_marker('somepath/.wh.foo')
    True
    >>> is_whiteout_marker('somepath/.wh.foo/')
    True
    """
    file_name = path and os.path.basename(path.strip('/')) or ''
    return file_name.startswith(WHITEOUT_EXPLICIT_PREFIX)


def get_whiteable_path(path):
    """
    Return the whiteable path for ``path`` or None if this not a whiteable path.
    TODO: Handle OSses with case-insensitive FS (e.g. Windows)
    """
    file_name = os.path.basename(path)
    parent_dir = os.path.dirname(path)

    if file_name == WHITEOUT_OPAQUE_PREFIX:
        # Opaque whiteouts means the whole parent directory should be removed
        # https://github.com/opencontainers/image-spec/blob/master/layer.md#whiteouts
        return parent_dir

    if file_name.startswith(WHITEOUT_EXPLICIT_PREFIX):
        # Explicit, file-only whiteout
        # https://github.com/opencontainers/image-spec/blob/master/layer.md#whiteouts
        _, _, real_file_name = file_name.rpartition(WHITEOUT_EXPLICIT_PREFIX)
        return os.path.join(parent_dir, real_file_name)


def find_whiteouts(root_location, walker=os.walk):
    """
    Yield a two-tuple of:
     - whiteout marker file location
     - corresponding file or directory path, relative to the root_location

    found under the `root_location` directory.

    `_walker` is a callable that behaves the same as `os.walk() and is used
    for testing`
    """
    for top, _dirs, files in walker(root_location):
        for fil in files:
            whiteout_marker_loc = os.path.join(top, fil)
            whiteable_path = get_whiteable_path(whiteout_marker_loc)
            if whiteable_path:
                whiteable_path = whiteable_path.replace(
                    root_location, '').strip(os.path.sep)
                yield whiteout_marker_loc, whiteable_path

# Set of well known file and directory paths found at the root of a filesystem


LINUX_PATHS = set([
    'usr',
    'etc',
    'var',
    'home',
    'sbin',
    'sys',
    'lib',
    'bin',
    'vmlinuz',
])

WINDOWS_PATHS = set([
    'Program Files',
    'Program Files(x86)',
    'Windows',
    'ProgramData',
    'Users',
    '$Recycle.Bin',
    'PerfLogs',
    'System Volume Information',
])


def compute_path_depth(root_path, dir_path):
    """
    Compute the depth of ``dir_path`` below ``root_path`` as the number of paths
    segments that extend below the root.
    """
    if not dir_path:
        return 0
    dir_path = dir_path.strip('/')

    if not root_path:
        return len(split(dir_path))

    root_path = root_path.strip('/')

    suffix = dir_path[len(root_path):]
    return len(split(suffix))


def find_root(
    location,
    max_depth=3,
    root_paths=LINUX_PATHS,
    min_paths=2,
    walker=os.walk,
):
    """
    Return the first likely location of the root of a filesystem found in the
    ``location`` directory and below up and including to ``max_depth`` directory
    levels deep below the ``location`` root directory.

    If ``max_depth`` == 0, look at full depth.

    Search for well known directories listed in the ``root_paths`` set. A root
    directory is returned as found if at least ``min_paths`` exists as filenames
    or directories under it.

    ``walker`` is a callable behaving like ``os.walk()`` and is used for testing.
    """
    if TRACE: logger.debug(
        f'find_root: location={location!r}, max_depth={max_depth!r}, '
        f'root_paths={root_paths!r}, min_paths={min_paths!r}'
    )
    depth = 0
    for top, dirs, files in walker(location):
        if TRACE: logger.debug(f' find_root: top={top!r}, dirs={dirs!r}, files={files!r}')
        if max_depth:
            depth = compute_path_depth(location, top)
            if TRACE: logger.debug(f'  find_root: top depth={depth!r}')
            if depth > max_depth:
                if TRACE: logger.debug(
                    f'    find_root: max_depth={max_depth!r}, '
                    f'depth={depth!r} returning None')
                return

        matches = len(set(dirs + files) & root_paths)
        if TRACE: logger.debug(f'  find_root: top={top!r}, matches={matches!r}')

        if matches >= min_paths:
            if TRACE: logger.debug(f'    find_root: matches >= min_paths: returning {top!r}')
            return top

    if TRACE: logger.debug(f'find_root: noting found: returning None')
