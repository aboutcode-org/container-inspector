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

import json
import logging
import hashlib
from os import path
from os import remove as os_remove
from os import rmdir as os_rmdir
import shutil
import os


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
        data = json.load(loc)
    return data


def get_command(cmd):
    """
    Clean the `cmd` list of command elements as found in the layer history.
    """
    # FIXME: this need to be cleaned further
    return cmd and ' '.join(
        [c for c in cmd if not c.startswith(('/bin/sh', '-c',))]) or ''


def sha256_digest(location):
    """
    Return a SHA256 checksum for the file content at location.
    """
    with open(location, 'rb') as loc:
        sha256 = hashlib.sha256(loc.read())
    return location and str(sha256.hexdigest())


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
    Return a mapping of unique labels from the merged config and container_config
    mappings
    """
    labels = set()

    config_labels = config.get('Labels', {}) or {}
    labels.update(config_labels.items())

    container_labels = (container_config.get('Labels', {}) or {})
    labels.update(container_labels.items())
    return dict(sorted(labels))


def extract_tar(location, target_dir):
    """
    Extract a tar archive at `location` in the `target_dir` directory.
    Ignore special device files.
    Do not preserve the permissions and owners.
    Raise exceptions on possible problematic relative paths.
    """
    import tarfile
    with tarfile.open(location) as tarball:
        # never extract character device, block and fifo files:
        # we extract dirs, files and links
        to_extract = [tinfo for tinfo in tarball.getmembers() if not tinfo.isdev()]
        # force a u+rwx on all files
        for tinfo in to_extract:
            tinfo.mode = 0o700
            # no absolute nor relative paths:
            # if tinfo.name != path.normpath(tinfo.name).lstrip('./\\'):
            #     raise Exception('Illegal tar member file path: {}'.format(tinfo.name))
            # if tinfo.linkname != path.normpath(tinfo.linkname).lstrip('./\\'):
            #     raise Exception('Illegal tar member file path link from: {} to: {}'.format(tinfo.name, tinfo.linkname))
        tarball.extractall(target_dir, members=to_extract)


def _rm_handler(function, path, excinfo):  # @UnusedVariable
    """
    shutil.rmtree handler invoked on error when deleting a directory tree.
    This retries deleting once before giving up.
    """
    if function == os_rmdir:
        try:
            shutil.rmtree(path, True)
        except Exception:
            pass

        if path.exists(path):
            logger.warning('Failed to delete directory %s', path)

    elif function == os_remove:
        try:
            delete(path, _err_handler=None)
        except:
            pass

        if path.exists(path):
            logger.warning('Failed to delete file %s', path)


def delete(location, _err_handler=_rm_handler):
    """
    Delete a directory or file at `location` recursively. Similar to "rm -rf"
    in a shell or a combo of os.remove and shutil.rmtree.
    """
    if not location:
        return

    if path.exists(location) or path.islink(location):
        if path.isdir(location):
            shutil.rmtree(location, False, _rm_handler)
        else:
            os_remove(location)


def copytree(src, dst):
    """
    Copy recursively the `src` directory to the `dst` directory. If `dst` is an
    existing directory, files in `dst` may be overwritten during the copy.
    """
    names = os.listdir(src)

    if not os.path.exists(dst):
        os.makedirs(dst)

    for name in names:
        srcname = os.path.join(src, name)
        dstname = os.path.join(dst, name)

        if path.isdir(srcname):
            copytree(srcname, dstname)
        elif path.isfile(srcname):
            copyfile(srcname, dstname)


def copyfile(src, dst):
    """
    Copy src file to dst file
    """
    assert path.isfile(src)
    if path.isdir(dst):
        dst = path.join(dst, path.basename(src))
    shutil.copyfile(src, dst)
