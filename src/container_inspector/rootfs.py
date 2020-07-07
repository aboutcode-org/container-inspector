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

from __future__ import print_function
from __future__ import absolute_import
from __future__ import unicode_literals

import logging
import os
from os import path
import tempfile

from container_inspector import LAYER_TAR_FILE
from container_inspector import utils


logger = logging.getLogger(__name__)
# un-comment these lines to enable logging
# import sys
# logging.basicConfig(level=logging.DEBUG, stream=sys.stdout)
# logger.setLevel(logging.DEBUG)

"""
Utilities to handle image and layer archives and recreate proper rootfs
from these archives.
"""


class InconsistentLayersError(Exception):
    pass


def rebuild_rootfs(img, target_dir):
    """
    Extract and merge all layers of the `image` Image in `target_dir`.
    Extraction is done in sequence from bottom (root) to top (latest layer)
    and the "whiteout" unionfs/overlayfs procedure is applied at each step
    as per the OCI spec:
        https://github.com/opencontainers/image-spec/blob/master/layer.md#whiteouts

    Return a list of deleted "whiteout" files.

    The extraction process consists of these steps:
     - extract the layer in a temp directory
     - find whiteouts in that layer temp dir
     - remove files/directories corresponding to these whiteouts in the target directory
     - remove whiteouts special marker files or dirs in the tempdirectory
     - move layer to the target directory, overwriting existing files

    See also some related implementations and links:
    https://github.com/moby/moby/blob/d1f470946/pkg/archive/whiteouts.go
    https://github.com/virt-manager/virt-bootstrap/commit/8a7e752d6614f8425874adbbdab16443ee0b1d9b
    https://github.com/goldmann/docker-squash


    https://github.com/moby/moby/blob/master/image/spec/v1.md
    https://github.com/moby/moby/blob/master/image/spec/v1.1.md
    https://github.com/moby/moby/blob/master/image/spec/v1.2.md
    """

    assert path.isdir(target_dir)
    assert path.exists(target_dir)
    extract_errors = []
    # log  deletions
    deletions = []

    for layer_num, layer in enumerate(img.layers):
        layer_id = layer.layer_id
        layer_tarball = path.join(img.base_location, layer_id, LAYER_TAR_FILE)
        logger.debug('Extracting layer {layer_num} tarball: {layer_tarball}'.format(**locals()))
        temp_target = tempfile.mkdtemp('container_inspector-docker')

        # 1. extract a layer to temp.
        # Note that we are not preserving any special file and any file permission
        utils.extract_tar(location=layer_tarball, target_dir=temp_target)
        logger.debug('  Extracted layer to: {}'.format(temp_target))

        # 2. find whiteouts in that layer.
        layer_whiteouts = list(find_whiteouts(temp_target))
        logger.debug('  Merging extracted layers and applying AUFS whiteouts/deletes')
        logger.debug('  Whiteouts:\n' + '     \n'.join(map(repr, layer_whiteouts)))

        # 3. remove whiteouts in the previous layer stack (e.g. the WIP rootfs)
        for layer_whiteout_marker, target_whiteable_path in layer_whiteouts:
            logger.debug('    Deleting whiteout dir or file: {target_whiteable_path}'.format(**locals()))
            whiteable = path.join(target_dir, target_whiteable_path)
            utils.delete(whiteable)
            # also delete the whiteout marker file
            utils.delete(layer_whiteout_marker)
            deletions.extend(target_whiteable_path)

        # 4. finall copy/overwrite the extracted layer over the WIP rootfs
        logger.debug('  Moving extracted layer from: {temp_target} to: {target_dir}'.format(**locals()))
        utils.copytree(temp_target, target_dir)
        logger.debug('  Moved layer to: {}'.format(target_dir))
        utils.delete(temp_target)

    return deletions


WHITEOUT_EXPLICIT_PREFIX = '.wh.'
WHITEOUT_OPAQUE_PREFIX = ('.wh..wh.opq')


def get_whiteout_marker_type(file_name):
    """
    Return the type of whiteout or False if the file_name is a whiteout marker file.
    """
    if file_name == WHITEOUT_OPAQUE_PREFIX:
        return WHITEOUT_OPAQUE_PREFIX
    if file_name.startswith(WHITEOUT_EXPLICIT_PREFIX):
        return WHITEOUT_EXPLICIT_PREFIX


def get_whiteable_path(location):
    """
    Given a location path string, return the whiteable path for this `location`
    or None.
    """
    file_name = path.basename(location)
    parent_dir = path.dirname(location)

    wh_marker_type = get_whiteout_marker_type(file_name)

    if wh_marker_type == WHITEOUT_OPAQUE_PREFIX:
        # Opaque whiteouts means the whole parent direvtory should be removed
        # https://github.com/opencontainers/image-spec/blob/master/layer.md#whiteouts
        return parent_dir

    elif wh_marker_type == WHITEOUT_EXPLICIT_PREFIX:
        # Explicit, file-only whiteout
        # https://github.com/opencontainers/image-spec/blob/master/layer.md#whiteouts
        _, _, real_file_name = file_name.rpartition(WHITEOUT_EXPLICIT_PREFIX)
        return path.join(parent_dir, real_file_name)


def find_whiteouts(base_location):
    """
    Yield tuple of (whiteout location, `base_location`-relative path of things to delete)
    found in the list of `locations` path strings.
    Does not access filesystem.
    """
    for top, _dirs, files in os.walk(base_location, base_location):
        for f in files:
            location = path.join(top, f)
            whiteable_path = get_whiteable_path(location)
            if whiteable_path:
                relative_path = whiteable_path.replace(base_location, '').strip('/')
                yield location, relative_path
