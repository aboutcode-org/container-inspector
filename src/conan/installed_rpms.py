# Copyright (c) nexB Inc. and others. All rights reserved.
# http://nexb.com and https://github.com/nexB/conan/
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
import subprocess
import sys

import click
import unicodecsv


logger = logging.getLogger(__name__)
# un-comment these lines to enable logging
# logging.basicConfig(level=logging.DEBUG, stream=sys.stdout)
# logger.setLevel(logging.INFO)


"""
Analysis helper for dynamic introspection of Docker images as installed locally.
"""

def installed_images(image_id=None):
    """
    Return a list of locally installed Docker images as a three tuple of (name,
    tag, image id).
    """
    # REPOSITORY                  TAG                 IMAGE ID            CREATED             VIRTUAL SIZE
    # mine/my-cloud               1.4.0.45            9b63d7aa7390        10 weeks ago        296.9 MB
    stdout = subprocess.check_output(['docker', 'images', '--no-trunc'])
    # we just skip if things do not run OK.
    # skip the first header line
    for line in stdout.splitlines(False)[1:]:
        # split on spaces and keep the first three elements
        name, tag, imid = line.split()[:3]
        imid = get_real_id(imid)
        logger.info('installed_images: %(name)s, %(tag)s, %(imid)s' % locals())
        if not image_id or (image_id and imid.startswith(image_id)):
            yield name, tag, imid


def get_real_id(imid):
    """
    Return bare id. Remove hash algo prefix from image or layer id if present (such
    as sha256:).
    """
    if ':' in imid:
        _hash, _, imid = imid.partition(':')
    return imid


def installed_image_history(image_id):
    """
    Return a list of ordered installed Docker layers ID given an image id as a
    tuple of (layer id, comment). The history is from latest to oldest.
    """
    # lines format
    # IMAGE               CREATED             CREATED BY                                      SIZE                COMMENT
    # 9b63d75a7390        10 weeks ago        /bin/sh -c #(nop) CMD [/bin/sh -c /startConfd   0 B
    stdout = subprocess.check_output(['docker', 'history', '--no-trunc', image_id])
    # we just skip if things do not run OK.
    # skip the first header line
    for line in stdout.splitlines(False)[1:]:
        # progressively partition on two spaces
        layer_id, _, right = line.partition('  ')
        _, _, right = right.strip().partition('  ')
        layer_command, _, right = right.strip().partition('  ')
        _size, _, right = right.strip().partition('  ')
        _comment = right.strip()
        yield get_real_id(layer_id), layer_command


def installed_rpms(image_id):
    """
    Return a list of installed RPMs in an installed Docker image id.
    """
    # lines format: one rpm as NVRA per line
    stdout = subprocess.check_output(['docker', 'run', image_id, 'rpm', '--query', '--all'])
    # we just skip if things do not run OK.
    return stdout.splitlines(False)


def installed_rpms_by_image_layer(image_id=None):
    """
    Return  tuples of (image id, image name, layer id, layer_order, layer_command unique RPM file names newly installed
    in this layer.
    All available images in the local Docker installation are probed in layer sequence.
    """
    for name, tag, image_id in installed_images(image_id):
        # track what is already installed in lower layers
        seen = set()
        # iterate layers in reverse to start from oldest to newest
        for layer_order, layer in enumerate(reversed(list(installed_image_history(image_id)))):
            layer_id, layer_command = layer
            for rpm in installed_rpms(layer_id):
                if rpm not in seen:
                    yield image_id, name, tag, layer_id, layer_order, layer_command, rpm + '.rpm'
                    seen.add(rpm)


@click.command()
@click.option('-i', '--image-id', default=None,
    help='Limit the data collection only to this image id. Run docker images '
         '--no-trunc to list the full image ids.')

@click.help_option('-h', '--help')
def conan_rpms(image_id=None):
    """
    Query the local Docker installation to find all newly installed RPMs in a given
    layer. All available images and layers in your local Dcoker installation are
    queried.

    An RPM version is  listed only in the layer where it is first installed (or first updated).

    Results are printed to stdout as CSV with these columns:

    image_id,image_name,image_tag,layer_id,layer_order,layer_command,installed_rpm_file

    Note that if a layer does not contain RPMs or is not for an RPM-based distro the results may be empty.

    The rows are repeated for each RPM found.
    Output is printed to stdout. Use a ">" redirect to save in a file.
    """
    headers = 'image_id image_name image_tag layer_id layer_order layer_command installed_rpm_file'.split()
    data = installed_rpms_by_image_layer(image_id)
    w = unicodecsv.UnicodeWriter(sys.stdout, encoding='utf-8')
    w.writerow(headers)
    w.writerows(data)
