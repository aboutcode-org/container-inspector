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

import json
import logging
import os
from os.path import join
import sys

import click
import unicodecsv

from commoncode import fileutils

from conan import DEFAULT_ID_LEN
from conan.dockerfile import flatten_dockerfiles
from conan.dockerfile import collect_dockerfiles
from conan.image_v10 import ImageV10
from conan.image_v11 import Registry
from conan.rootfs import rebuild_rootfs


logger = logging.getLogger(__name__)
# un-comment these lines to enable logging
# logging.basicConfig(level=logging.DEBUG, stream=sys.stdout)
# logger.setLevel(logging.DEBUG)


def get_image_v10(location, echo=print, layerid_len=DEFAULT_ID_LEN):
    """
    Return a dictionary location -> image object if the location is an ImageV10
    directory. Return an empty dictionary otherwise.
    """
    try:
        image = ImageV10(location, layerid_len=layerid_len)
        echo('Found Docker image at: %(location)r' % locals())
        return {location: image}
    except Exception, e:
        logger.debug('get_image_v10: Not an image directory: %(location)r' % locals())
        # not an image
        return {}


def collect_images_v10(location, echo=print, layerid_len=DEFAULT_ID_LEN):
    """
    Collect all images in a directory tree. Return a map of location ->
    Image
    """
    images = {}
    for top, dirs, files in fileutils.walk(location):
        image = get_image_v10(top, echo, layerid_len=layerid_len)
        logger.debug('collect_images_v10: image: %(image)r' % locals())
        images.update(image)

        for d in dirs:
            image = get_image_v10(join(top, d), echo, layerid_len=layerid_len)
            logger.debug('collect_images_v10: image: %(image)r' % locals())
            images.update(image)
    logger.debug('collect_images_v10: images: %(images)r' % locals())
    return images


def collect_and_rebuild_rootfs_v10(location, echo=print, layerid_len=DEFAULT_ID_LEN):
    """
    Collect all images in a directory tree. Extract/merges the layers side-by-
    side with the image directory with an extract suffix.
    """
    import extractcode
    all_wh = {}
    # FIXME: we should instead receive a list of images....

    for loc, image in collect_images_v10(location, echo, layerid_len=layerid_len).items():
        extract_target = loc.rstrip('\\/') + extractcode.EXTRACT_SUFFIX
        fileutils.create_dir(extract_target)
        echo('Extracting/merging and building rootfs from layers for Docker image %(loc)r \n  to: %(extract_target)r' % locals())
        errors, whiteouts = rebuild_rootfs(image, extract_target, layerid_len=layerid_len)
        if whiteouts:
            echo('Files deleted while extract/merging layers for Docker image %(loc)r:' % locals())
            all_wh[loc] = whiteouts
            for w in whiteouts:
                echo(' ' + w)
        if errors:
            echo('Extraction error for layers of Docker image %(loc)r:' % locals())
            for e in errors:
                echo(' ' + e)
    return all_wh


def graph_images(images):
    """
    Build a graph of Docker images and layers.
    """
    pass


def no_print(*args, **kwargs):
    pass



@click.command()
@click.argument('directory', type=click.Path(exists=True, readable=True))
@click.option('-e', '--extract', is_flag=True, is_eager=True,
              help=('Find built Docker images and their layers. For each image found, '
                   'extract and merge all layers in a single rootfs-like structure.'))
@click.option('--image-json', is_flag=True, is_eager=True,
              help='Find built Docker images and their layers. Print information as JSON.')
@click.option('-c', '--image-csv', is_flag=True, is_eager=True,
              help='Find built Docker images and their layers. Print information as CSV.')
@click.option('--dockerfile-json', is_flag=True, is_eager=True,
              help='Find source Dockerfile files. Print information as JSON.')
@click.option('-d', '--dockerfile-csv', is_flag=True, is_eager=True,
              help='Find source Dockerfile files. Print information  as CSV.')
@click.option('-l', '--layerid-len', default=DEFAULT_ID_LEN,
              help='Use a different layer ID length than the default 64 characters to avoid very long ids.')
@click.help_option('-h', '--help')
def conan(directory, extract=False,
           image_json=False, image_csv=False,
           dockerfile_json=False, dockerfile_csv=False,
           layerid_len=DEFAULT_ID_LEN):
    """
    Search and collect Docker images data in DIRECTORY.

    Based on the provided options either:
    - print information about the Docker images and their layers (printed in
      sequence) as JSON or CSV.
    - print information about Dockerfiles as JSON or CSV.
    - rebuild the rootfs of images (e.g. extract and merge and layers) in a
      "-extract" directory and print results.

    Output is printed to stdout. Use a ">" redirect to save in a file.
    """
    loc = os.path.abspath(os.path.expanduser(directory))
    if extract:
        collect_and_rebuild_rootfs_v10(loc, echo=click.echo)

    elif image_json or image_csv:
        images = collect_images_v10(loc, echo=no_print, layerid_len=layerid_len)
        if image_json:
            click.echo(json.dumps([image.as_dict() for _loc, image in images.items()], indent=2))
        else:
            images = [list(image.as_flat_dict()) for _, image in images.items()]
            if images:
                keys = images[0][0].keys()
                w = unicodecsv.DictWriter(sys.stdout, keys, encoding='utf-8')
                w.writeheader()
                for d in images:
                    for i in d:
                        w.writerow(i)

    elif dockerfile_json or dockerfile_csv:
        dockerfiles = collect_dockerfiles(loc, echo=no_print)
        if dockerfile_json:
            click.echo(json.dumps([df for _loc, df in dockerfiles.items()], indent=2))
        else:
            if dockerfiles:
                dockerfiles = list(flatten_dockerfiles(dockerfiles))
                keys = dockerfiles[0].keys()
                w = unicodecsv.DictWriter(sys.stdout, keys, encoding='utf-8')
                w.writeheader()
                for df in dockerfiles:
                    w.writerow(df)



@click.command()
@click.argument('directory', type=click.Path(exists=True, readable=True))
@click.option('-r', '--repos', is_flag=True, default=True,
              help='Find Docker repos, their images and their layers. Print information as JSON.')
@click.option('--csv', is_flag=True, default=False, 
              help='Print information as csv instead of JSON.') 
@click.help_option('-h', '--help')
def conanv11(directory, repos=True, csv=False):
    """
    Search and collect Docker repos and images data in DIRECTORY.

    Output is printed to stdout. Use a ">" redirect to save in a file.
    """
    loc = os.path.abspath(os.path.expanduser(directory))
    if not repos:
        return 

    registry = Registry()
    registry.populate(loc)

    if csv:
        #click.echo(json.dumps(list(registry.flatten()), indent=2))
        flat_reg = list(registry.flatten())
        if not flat_reg:
            return
        keys = flat_reg[0].keys()
        w = unicodecsv.DictWriter(sys.stdout, keys, encoding='utf-8')
        w.writeheader()
        for f in flat_reg:
            w.writerow(f)
    else:
        click.echo(json.dumps(registry.as_dict(), indent=2))
