#
# Copyright (c) nexB Inc. and others. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
# See http://www.apache.org/licenses/LICENSE-2.0 for the license text.
# See https://github.com/nexB/container-inspector for support or download.
# See https://aboutcode.org for more information about nexB OSS projects.
#

import logging
import os
import sys
import tempfile
import csv as csv_module
import json as json_module
from os import path

import click

from container_inspector import image
from container_inspector import dockerfile
from container_inspector import rootfs

TRACE = False
logger = logging.getLogger(__name__)
if TRACE:
    logging.basicConfig(level=logging.DEBUG, stream=sys.stdout)
    logger.setLevel(logging.DEBUG)


@click.command()
@click.argument('image_path', metavar='IMAGE_path', type=click.Path(exists=True, readable=True))
@click.argument('extract_directory', metavar='TARGET_DIR', type=click.Path(exists=True, writable=True))
@click.help_option('-h', '--help')
def container_inspector_squash(image_path, extract_directory):
    """
    Given a Docker image at IMAGE_PATH, extract and squash that image in TARGET_DIR
    merging all layers in a single rootfs-like structure.'))
    """
    _container_inspector_squash(image_path, extract_directory)


def _container_inspector_squash(image_path, extract_directory):
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
def container_inspector_dockerfile(directory, json=False, csv=False):
    """
    Find source Dockerfile files in DIR. Print information as JSON or CSV to stdout.
    Output is printed to stdout. Use a ">" redirect to save in a file.
    """
    _container_inspector_dockerfile(directory, json, csv)


def _container_inspector_dockerfile(directory, json=False, csv=False):
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
        w = csv_module.DictWriter(sys.stdout, keys)
        w.writeheader()
        for df in dockerfiles:
            w.writerow(df)


@click.command()
@click.argument('image_path', metavar='IMAGE_PATH', type=click.Path(exists=True, readable=True))
@click.option('--extract-to', default=None, metavar='PATH', type=click.Path(exists=True, readable=True))
@click.option('--csv', is_flag=True, default=False, help='Print information as CSV instead of JSON.')
@click.help_option('-h', '--help')
def container_inspector(image_path, extract_to=None, csv=False):
    """
    Find Docker images and their layers in IMAGE_PATH.
    Print information as JSON by default or as CSV with --csv.
    Optionally extract images with extract-to.
    Output is printed to stdout. Use a ">" redirect to save in a file.
    """
    results = _container_inspector(image_path, extract_to=extract_to, csv=csv)
    click.echo(results)


def _container_inspector(image_path, extract_to=None, csv=False):
    images = get_images_from_dir_or_tarball(image_path, extract_to=extract_to)
    as_json = not csv

    if as_json:
        images = [i.to_dict() for i in images]
        return json_module.dumps(images, indent=2)
    else:
        from io import StringIO
        output = StringIO()
        flat = list(image.flatten_images_data(images))
        if not flat:
            return
        keys = flat[0].keys()
        w = csv_module.DictWriter(output, keys)
        w.writeheader()
        for f in flat:
            w.writerow(f)
        val = output.getvalue()
        output.close()
        return val


def get_images_from_dir_or_tarball(image_path, extract_to=None, quiet=False):
    image_loc = os.path.abspath(os.path.expanduser(image_path))
    if path.isdir(image_path):
        images = image.Image.get_images_from_dir(image_loc)
    else:
        # assume tarball
        extract_to = extract_to or tempfile.mkdtemp()
        images = image.Image.get_images_from_tarball(
            archive_location=image_loc,
            extracted_location=extract_to,
            verify=True,
        )

        for img in images:
            img.extract_layers(extracted_location=extract_to)
        if not quiet:
            click.echo('Extracting image tarball to: {}'.format(extract_to))
    return images
