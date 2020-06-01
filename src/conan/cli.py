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

import json as json_module
import logging
import os
from os import path
import sys
import tempfile

import click
import unicodecsv

from conan import image
from conan import dockerfile
from conan import rootfs


logger = logging.getLogger(__name__)
# un-comment these lines to enable logging
# logging.basicConfig(level=logging.DEBUG, stream=sys.stdout)
# logger.setLevel(logging.DEBUG)


@click.command()
@click.argument('image_path', metavar='IMAGE_path', type=click.Path(exists=True, readable=True))
@click.argument('extract_directory', metavar='TARGET_DIR', type=click.Path(exists=True, writable=True))
@click.help_option('-h', '--help')
def conan_squash(image_path, extract_directory):
    """
    Given a Docker image at IMAGE_PATH, extract and squash that image in TARGET_DIR
    merging all layers in a single rootfs-like structure.'))
    """
    _conan_squash(image_path, extract_directory)


def _conan_squash(image_path, extract_directory):
    images = get_images_from_dir_or_tarball(image_path)
    assert len(images) == 1, 'Can only squash one image at a time'
    img = images[0]
    target_loc = os.path.abspath(os.path.expanduser(extract_directory))
    rootfs.rebuild_rootfs(img, target_loc)


@click.command()
@click.argument('directory', metavar='DIR', type=click.Path(exists=True, readable=True))
@click.option('--json', is_flag=True, help='Print information as JSON.')
@click.option('--csv', is_flag=True, help='Print information  as CSV.')
@click.help_option('-h', '--help')
def conan_dockerfile(directory, json=False, csv=False):
    """
    Find source Dockerfile files in DIR. Print information as JSON or CSV to stdout.
    Output is printed to stdout. Use a ">" redirect to save in a file.
    """
    _conan_dockerfile(directory, json, csv)


def _conan_dockerfile(directory, json=False, csv=False):
    assert json or csv, 'At least one of --json or --csv is required.'
    dir_loc = os.path.abspath(os.path.expanduser(directory))

    dockerfiles = dockerfile.collect_dockerfiles(location=dir_loc)
    if not dockerfiles:
        return
    if json:
        click.echo(json_module.dumps([df for _loc, df in dockerfiles.items()], indent=2))

    if csv:
        dockerfiles = list(dockerfile.flatten_dockerfiles(dockerfiles))
        keys = dockerfiles[0].keys()
        w = unicodecsv.DictWriter(sys.stdout, keys, encoding='utf-8')
        w.writeheader()
        for df in dockerfiles:
            w.writerow(df)


@click.command()
@click.argument('image_path', metavar='IMAGE_path', type=click.Path(exists=True, readable=True))
@click.option('--csv', is_flag=True, default=False, help='Print information as csv instead of JSON.')
@click.help_option('-h', '--help')
def conan(image_directory, csv=False):
    """
    Find Docker images and their layers in IMAGE_PATH.
    Print information as JSON by default or as CSV with --csv.
    Output is printed to stdout. Use a ">" redirect to save in a file.
    """
    _conan(image_directory, csv)


def _conan(image_directory, tarball=False, csv=False):
    images = get_images_from_dir_or_tarball(image_directory)
    as_json = not csv

    if as_json:
        images = [i.to_dict() for i in images]
        click.echo(json_module.dumps(images, indent=2))
    else:
        flat = list(image.flatten_images(images))
        if not flat:
            return
        keys = flat[0].keys()
        w = unicodecsv.DictWriter(sys.stdout, keys, encoding='utf-8')
        w.writeheader()
        for f in flat:
            w.writerow(f)


def get_images_from_dir_or_tarball(image_directory):
    image_loc = os.path.abspath(os.path.expanduser(image_directory))
    if path.isdir(image_directory):
        images = list(image.Image.get_images_from_dir(image_loc))
    else:
    # assume tarball
        extract_dir = tempfile.mkdtemp()
        images = list(image.Image.get_images_from_tarball(image_loc, extract_dir))
        click.echo('Extracting image tarball to: {}'.format(extract_dir))
    return images
