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

import logging
import os
from os.path import join

from commoncode import fileutils
from commoncode import filetype

from conan import DEFAULT_ID_LEN
from conan import LAYER_TAR_FILE


logger = logging.getLogger(__name__)
# un-comment these lines to enable logging
# logging.basicConfig(level=logging.DEBUG, stream=sys.stdout)
# logger.setLevel(logging.DEBUG)

"""
Utilities to handle image and layer archives and recreate proper rootfs
from these archives.
"""


WHITEOUT_PREFIX = '.wh.'
WHITEOUT_SPECIAL_DIR_PREFIX = '.wh..wh.'
# TODO: we do not handle these yet (see the OCI spec)
# https://github.com/opencontainers/image-spec/blob/master/layer.md#whiteouts
WHITEOUT_OPAQUE_PREFIX = '.wh..wh.opq'


class InconsistentLayersError(Exception):
    pass


def rebuild_rootfs(image, target_dir, layerid_len=DEFAULT_ID_LEN):
    """
    Extract and merge all layers to target_dir. Extraction is done in
    sequence from bottom (root) to top (latest layer).

    Return a mapping of errors and a list of whiteouts/deleted files.

    The extraction process consists of these steps:
     - extract the layer in a temp directory
     - move layer to the target directory, overwriting existing files
     - if any, remove AUFS special files/dirs in the target directory
     - if any, remove whiteouts file/directory pairs in the target directory
    """

    from extractcode.extract import extract_file

    assert filetype.is_dir(target_dir)
    assert os.path.exists(target_dir)
    extract_errors = []
    # log whiteouts deletions
    whiteouts = []

    for layer_id, layer in image.layers.items():
        layer_tarball = join(image.repo_dir, layer_id[:layerid_len], LAYER_TAR_FILE)
        logger.debug('Extracting layer tarball: %(layer_tarball)r' % locals())
        temp_target = fileutils.get_temp_dir('conan-docker')
        # FIXME: we are not preserving links (hard and sym) nor any special file.
        xevents = list(extract_file(layer_tarball, temp_target))
        for x in xevents:
            if x.warnings or  x.errors:
                extract_errors.extend(xevents)

        # FIXME: the order of ops is WRONG: we are getting whiteouts incorrectly
        # it should be:
        # 1. extract a layer to temp.
        # 2. find whiteouts in that layer.
        # 3. remove whiteouts in the previous layer stack (e.g. the WIP rootfs)
        # 4. finall copy the extracted layer over the WIP rootfs

        # move extracted layer to target_dir
        logger.debug('Moving extracted layer from: %(temp_target)r to: %(target_dir)r')
        fileutils.copytree(temp_target, target_dir)
        fileutils.delete(temp_target)

        logger.debug('Merging extracted layers and applying AUFS whiteouts/deletes')
        for top, dirs, files in fileutils.walk(target_dir):
            # delete AUFS dirs and apply whiteout deletions
            for dr in dirs[:]:
                whiteable_dir = join(top, dr)
                if dr.startswith(WHITEOUT_PREFIX):
                    # delete the .wh. dir...
                    dirs.remove(dr)
                    logger.debug('Deleting whiteout dir: %(whiteable_dir)r' % locals())
                    fileutils.delete(whiteable_dir)

                    # ... and delete the corresponding dir it does "whiteout"
                    base_dir = dr[len(WHITEOUT_PREFIX):]
                    try:
                        dirs.remove(base_dir)
                    except ValueError:
                        # FIXME: should we really raise an exception here?
                        msg = ('Inconsistent layers: '
                               'missing directory to whiteout: %(base_dir)r' % locals())
                        raise InconsistentLayersError(msg)
                    wdo = join(top, base_dir)
                    logger.debug('Deleting real dir:  %(wdo)r' % locals())
                    fileutils.delete(wdo)
                    whiteouts.append(wdo)

                # delete AUFS special dirs
                elif dr.startswith(WHITEOUT_SPECIAL_DIR_PREFIX):
                    dirs.remove(dr)
                    logger.debug('Deleting AUFS special dir:  %(whiteable_dir)r' % locals())
                    fileutils.delete(whiteable_dir)

            # delete AUFS files and apply whiteout deletions
            all_files = set(files)
            for fl in all_files:
                whiteable_file = join(top, fl)
                if fl.startswith(WHITEOUT_PREFIX):
                    # delete the .wh. marker file...
                    logger.debug('Deleting whiteout file: %(whiteable_file)r' % locals())
                    fileutils.delete(whiteable_file)
                    # ... and delete the corresponding file it does "whiteout"
                    # e.g. logically delete
                    base_file = fl[len(WHITEOUT_PREFIX):]

                    wfo = join(top, base_file)
                    whiteouts.append(wfo)
                    if base_file in all_files:
                        logger.debug('Deleting real file:  %(wfo)r' % locals())
                        fileutils.delete(wfo)

                # delete AUFS special files
                elif fl.startswith(WHITEOUT_SPECIAL_DIR_PREFIX):
                    logger.debug('Deleting AUFS special file:  %(whiteable_file)r' % locals())
                    fileutils.delete(whiteable_file)
                    whiteouts.append(whiteable_file)

    return extract_errors, whiteouts
