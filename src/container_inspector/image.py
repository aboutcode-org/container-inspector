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
import os
from os import path

import attr

from container_inspector import LAYER_JSON_FILE
from container_inspector import LAYER_TAR_FILE
from container_inspector import LAYER_VERSION_FILE
from container_inspector import MANIFEST_JSON_FILE

from container_inspector.utils import as_bare_id
from container_inspector.utils import load_json
from container_inspector.utils import sha256_digest
from container_inspector import utils
from container_inspector.distro import Distro

logger = logging.getLogger(__name__)
# un-comment these lines to enable logging
# logging.basicConfig(level=logging.DEBUG, stream=sys.stdout)
# logger.setLevel(logging.DEBUG)


def logger_debug(*args):
    return logger.debug(' '.join(isinstance(a, str) and a or repr(a) for a in args))

"""
Objects to handle Docker repositories, images and layers data in v1.1 and v1.2 format.

The Docker Image Specifications are at:
- https://github.com/moby/moby/blob/master/image/spec/v1.md
- https://github.com/moby/moby/blob/master/image/spec/v1.1.md
- https://github.com/moby/moby/blob/master/image/spec/v1.2.md

The OCI specs:
- https://github.com/opencontainers/image-spec/blob/master/spec.md
https://github.com/opencontainers/image-spec/blob/master/image-layout.md
- https://github.com/opencontainers/image-spec/blob/master/layer.md#whiteouts


The Docker Manifest Specifications are at:
- https://github.com/docker/distribution/blob/master/docs/spec/deprecated-schema-v1.md
- https://github.com/docker/distribution/blob/master/docs/spec/manifest-v2-1.md
- https://github.com/docker/distribution/blob/master/docs/spec/manifest-v2-2.md

The OCI specs:
- https://github.com/opencontainers/image-spec/blob/master/manifest.md


The model shape is:
    - Registry
      - repositories as a list of Repository
      - Repository
        - images_by_id with {id: Image}
        - layers_by_id with {id: Layer}
        - Image
          - layers as a list of Layer
          - Layer
            - tarball and files
"""


class ToDictMixin(object):
    """
    A mixin to add an to_dict() method to an attr-based class.
    """

    def to_dict(self):
        return attr.asdict(self)


def flatten_images(images):
    """
    Yield mapping for each layer of each image of an `images` list of Image.
    This is a flat data structure for csv output.
    """
    for img in images:
        base_data = dict([
            ('image_dir', img.base_location),
            ('image_id', img.image_id),
            ('image_tags', ','.join(img.tags)),
        ])
        for layer in img.layers:
            layer_data = dict(base_data)
            layer_data['author'] = layer.author
            layer_data['created_by'] = layer.created_by
            layer_data['layer_id'] = layer.layer_id
            layer_data['layer_sha256'] = layer.layer_sha256
            layer_data['is_empty_layer'] = layer.is_empty_layer
            if layer.layer_id:
                ld = path.join(img.base_location, layer.layer_id)
            else:
                ld = None
            layer_data['layer_location'] = ld
            yield layer_data


@attr.attributes
class ConfigMixin(object):
    """
    Configuration data. Shared definition as found in a layer json file and an image
    config json file.
    """
    docker_version = attr.attrib(
        default=None,
        metadata=dict(doc='The docker version.')
    )

    os = attr.attrib(
        default=None,
        metadata=dict(doc='Operating system.')
    )

    architecture = attr.attrib(
        default=None,
        metadata=dict(doc='architecture.')
    )

    created = attr.attrib(
        default=None,
        metadata=dict(doc='Time stamp when this was created')
    )

    author = attr.attrib(
        default=None,
        metadata=dict(doc='Author when present')
    )

    comment = attr.attrib(
        default=None,
        metadata=dict(doc='comment')
    )

    labels = attr.attrib(
        default=attr.Factory(list),
        metadata=dict(doc='List of labels for this layer merged from the original config and container_config.')
    )

    @classmethod
    def from_config_data(cls, data):
        """
        Return a mapping of `data` suitable to use as kwargs from a layer
        or an image data mapping.
        """
        config = data.get('config', {})
        container_config = data.get('container_config', {})

        return dict(
            docker_version=data.get('docker_version'),
            os=data.get('os'),
            architecture=data.get('architecture'),
            created=data.get('created'),
            author=config.get('Author') or config.get('author'),
            comment=data.get('comment'),
            labels=utils.get_labels(config, container_config),
        )


@attr.attributes
class Image(ToDictMixin, ConfigMixin):
    """
    A container image with pointers to its layers.
    """

    base_location = attr.attrib(
        default=None,
        metadata=dict(doc='The directory location where this images is found')
    )

    image_id = attr.attrib(
        default=None,
        metadata=dict(doc='The id for this image. '
                      'This is the base name of the config json file '
                      'and is the same as non-prefixed digest for the config JSON file.'
                      'For legacy v1.0 images, this is the ID available in a '
                      'repositories JSON which is the top layer_id.')
    )

    parent_digest = attr.attrib(
        default=None,
        metadata=dict(doc='The digest of the parent for this image.')
    )

    config_digest = attr.attrib(
        default=None,
        metadata=dict(doc='The digest of the config JSON file for this image. '
                          'This is supposed to be the same as the id. '
                          'Not available for legacy V1.0 images')
    )

    layers = attr.attrib(
        default=attr.Factory(list),
        metadata=dict(doc='A list of layer objects from bottom to top, excluding empty layers. This is really the "rootfs"')
    )

    tags = attr.attrib(
        default=attr.Factory(list),
        metadata=dict(doc='List of tags for this image as strings of "user/name:version".')
    )

    history = attr.attrib(
        default=attr.Factory(list),
        metadata=dict(doc='List of mapping for the layers history. All layers are included including empty layers.')
    )

    distro = attr.attrib(
        default=None,
        metadata=dict(doc='The Distro object for this image.')
    )

    extracted_to_location = attr.attrib(
        default=None,
        metadata=dict(doc='The directory where this image has been extracted to.')
    )

    @property
    def top_layer(self):
        """
        The top layer for this image.
        """
        return self.layers[-1]

    @property
    def bottom_layer(self):
        """
        The bottom layer for this image.
        """
        return self.layers[0]

    def extract_layers(self, target_dir, force_extract=False):
        """
        Extract each layer tarball to the `target_dir` directory. A layer is
        extracted to its own directory named after its `layer_id`.

        If `force_extract` is False, do not extract a layer if its extraction
        directory already exists.
        """
        self.extracted_to_location = target_dir
        for layer in self.layers:
            layer.extract(
                target_dir=self.extracted_to_location,
                use_layer_id=True,
                force_extract=force_extract
            )

    def get_layers_resources(self, with_dir=False):
        """
        Yield a Resource for each file in each layer.
        """
        for layer in self.layers:
            for resource in layer.get_resources(with_dir):
                yield resource

    def get_and_set_distro(self):
        """
        Return a Distro object for this image. Raise exceptions if it cannot be built.
        """
        bottom_layer = self.bottom_layer
        if not bottom_layer.extracted_to_location:
            raise Exception('The image has not been extracted.')

        self.distro = Distro.from_rootfs(bottom_layer.extracted_to_location)
        return self.distro

    def cleanup(self):
        """
        Removed extracted layer files from self.extracted_to_location.
        """
        if self.extracted_to_location:
            utils.delete(self.extracted_to_location)

        for layer in self.layers:
            layer.extracted_to_location = None

        self.extracted_to_location = None

    def squash(self, target_dir):
        """
        Extract and squash all the layers of this image as a single rootfs rooted in the `target_dir` directory.
        If `use_layer_id` is True, extract in a dir named ``target_dir/layer_id/`
        Cache the location where this layer was last extracted in the
        self.extracted_to_location attribute
        """
        from container_inspector import rootfs
        rootfs.rebuild_rootfs(self, target_dir)

    def get_installed_packages(self, packages_getter):
        """
        Yield tuples of unique (package_url, package, layer) for installed
        packages found in that image's layers using the `packages_getter`
        function or callable. A package is reported in the layer its package_url
        is first seen.

        The `packages_getter()` function should:

        - accept a first argument string that is the root directory of
          filesystem of this the layer

        - yield tuples of (package_url, package) where package_url is a
          package_url string that uniquely identifies the package  and `package`
          is some object that represents the package (typically a scancode-
          toolkit packagedcode.models.Package class or some nested mapping with
          the same structure).

        An `packages_getter` function would typically query the
        system packages database (such as an RPM database or similar) to collect
        the list of installed system packages.
        """
        seen_packages = set()
        for layer in self.layers:
            for purl, package in layer.get_installed_packages(packages_getter):
                if purl in seen_packages:
                    continue
                seen_packages.add(purl)
                yield purl, package, layer

    @staticmethod
    def get_images_from_tarball(location, target_dir, force_extract=False):
        """
        Yield Image objects found in the tarball at `location` that will be
        extracted to `target_dir`. The tarball must be in the format of a "docker
        save" command tarball.
        If `force_extract` is False, do not extract to target_dir if target_dir
        already exists
        """
        if force_extract or not os.path.exists(target_dir):
            utils.extract_tar(location, target_dir)
        return Image.get_images_from_dir(target_dir)

    @staticmethod
    def get_images_from_dir(location):
        """
        Yield Image objects found in a base directory at `location`. The
        directory must contain a manifest.json and must be in the same format as
        a "docker save" extracted to `location`.


        The "manifest.json" JSON file for format v1.1/1.2. of saved Docker
        images.

        This file is a mapping with this shape:
        - The `Config` field references another JSON file in same directory
          that includes the image detailed data.
        - The `RepoTags` field lists references pointing to this image.
        - The `Layers` field points to the filesystem changeset tars, e.g. the
          path to the layer.tar files as a list of paths.
        - An optional `Parent` field references the imageID (as a sha256-prefixed
          digest?) of the parent image. This parent must be part of the same
          `manifest.json` file.

        For example:

        [
            {'Config': '7043867122e704683c9eaccd7e26abcd5bc9fea413ddfeae66166697bdcbde1f.json',
             'Layers': [
                 '768d4f50f65f00831244703e57f64134771289e3de919a576441c9140e037ea2/layer.tar',
                 '6a630e46a580e8b2327fc45d9d1f4734ccaeb0afaa094e0f45722a5f1c91e009/layer.tar',
                 ]
             'RepoTags': ['user/image:version'],
             "Parent": "sha256:5a00e6ccb81ef304e1bb9995ea9605f199aa96659a44237d58ca96982daf9af8"
             },

            {'Config': '7043867122e704683c9eaccd7e26abcd5bc9fea413ddfeae66166697bdcbde1f.json',
             'Layers': [
                 '768d4f50f65f00831244703e57f64134771289e3de919a576441c9140e037ea2/layer.tar',
                 '6a630e46a580e8b2327fc45d9d1f4734ccaeb0afaa094e0f45722a5f1c91e009/layer.tar',
                 ]
             'RepoTags': ['user/image:version']
             },
        ]
        """
        if not path.isdir(location):
            raise Exception('Not a directory: {}'.format(location))

        manifest_loc = path.join(location, MANIFEST_JSON_FILE)
        # NOTE: we are only looking at V1.1/2 repos layout for now and not the legacy v1.0.
        if not path.exists(manifest_loc):
            raise Exception('manifest.json file missing in {}'.format(location))

        manifest = load_json(manifest_loc)

        for manifest_config in manifest:
            yield Image.from_manifest_config(
                base_location=location,
                manifest_config=manifest_config,
                verify_config=False
            )

    @staticmethod
    def from_manifest_config(base_location, manifest_config, verify_config=False):
        """
        Return an Image object built from the JSON config file at `location` and
        the `manifest_config` data mapping (from a manifest.json).  The
        manifest_config[Config] JSON file is named after its SHA256 and there is
        one such file for each img.

        Each file has this shape:
        {
            'docker_version': '1.8.2',
            'os': 'linux',
            'architecture': 'amd64',
            'author': '<author name>',
            'created': '2016-09-30T10:16:27.109917034Z',
            'container': '1ee508bc7a35150c9e5924097a31dfb4b6b2ca1260deb6fd14cb03c53764e40b',

            # these two mappings are essentially similar: image_config is the
            # runtime image_config and container_config is the image_config as
            # it existed when the container was created.
            'image_config': { <some image_config k/v pairs> },
            'container_config': { <some image_config k/v pairs> },

            # array of objects describing the history of each layer.
            # The array is ordered from bottom-most layer to top-most layer.
            # but contains also entries for empty layers
            'history': [
                {'author': 'The CentOS Project <cloud-ops@centos.org> - ami_creator',
                 'created': '2015-04-22T05:12:47.171582029Z',
                 'created_by': '/bin/sh -c #(nop) MAINTAINER The CentOS Project <cloud-ops@centos.org> - ami_creator'
                 'comment': 'some comment (eg a commit message)',
                 'empty_layer': True or False (if not present, defaults to False.
                                True for empty, no-op layers with no rootfs content.
                },

                {'author': 'The CentOS Project <cloud-ops@centos.org> - ami_creator',
                 'created': '2015-04-22T05:13:47.072498418Z',
                 'created_by': '/bin/sh -c #(nop) ADD file:eab3c2991729003be2fad083bc2535fb4d03 in /'
                },
            ]
            # This is in order from bottom-most to top-most
            # each id is the sha256 of a layer.tar
            # NOTE: Empty layer may NOT have their digest listed here, so this list
            # may not align exactly with the history list:
            # e.g. this list only has entries if "empty_layer" is not set to True for that layer.

            'rootfs': {
                'diff_ids': [
                    'sha256:5f70bf18a086007016e948b04aed3b82103a36bea41755b6cddfaf10ace3c6ef',
                    'sha256:2436bc321ced91d2f3052a98ff886a2feed0788eb524b2afeb48099d084c33f5',
                    'sha256:cd141a5beb0ec83004893dfea6ea8508c6d09a0634593c3f35c0d433898c9322',]
                'type': u'layers'
            }
        }
        """
        config_file = manifest_config.get('Config') or ''
        config_file_loc = path.join(base_location, config_file)
        if not path.exists(config_file_loc):
            raise Exception('Invalid configuration. Missing Config file: {}'.format(config_file_loc))

        image_id, _ = path.splitext(path.basename(config_file_loc))
        config_digest = sha256_digest(config_file_loc)
        if verify_config:
            if image_id != as_bare_id(config_digest):
                logger.warning('WARNING: img config digest is not consistent.')
                config_digest = 'sha256:'.format(image_id)

        layer_paths = manifest_config.get('Layers') or []
        layers_locations = [path.join(base_location, layer_path) for layer_path in layer_paths]
        layers_by_sha256 = {sha256_digest(loc): loc for loc in layers_locations}

        parent_digest = manifest_config.get('Parent')
        tags = manifest_config.get('RepoTags') or []

        image_config = load_json(config_file_loc)
        rootfs = image_config.get('rootfs')

        history = image_config.get('history') or {}

        assert rootfs['type'] == 'layers', (
            'Unknown type for img rootfs: expecting "layers": {}'.format(config_file_loc))

        # TODO: add support for empty tarball as this may not work if there is a
        # diff for an empty layer with a digest for some EMPTY content e.g.
        # e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855

        layer_sha256s = [as_bare_id(layer_sha256) for layer_sha256 in rootfs['diff_ids']]

        layers = []
        for layer_sha256 in layer_sha256s:
            layer_location = layers_by_sha256[layer_sha256]
            lay = Layer(
                layer_sha256=layer_sha256,
                layer_location=layer_location,
                layer_size=path.getsize(layer_location))
            layers.append(lay)

        img = Image(
            base_location=base_location,
            image_id=image_id,
            layers=layers,
            config_digest=config_digest,
            parent_digest=parent_digest,
            history=history,
            tags=tags,
            **ConfigMixin.from_config_data(image_config)
        )

        return img


@attr.attributes
class Resource(ToDictMixin):
    path = attr.attrib(
        default=None,
        metadata=dict(doc='The root-relative path for this Resource.')
    )

    layer_path = attr.attrib(
        default=None,
        metadata=dict(doc='The relative path including the layer prefix.')
    )

    location = attr.attrib(
        default=None,
        metadata=dict(doc='The absolute location for this Resource.')
    )

    is_file = attr.ib(
        default=True,
        metadata=dict(doc='True for file, False for directory.')
    )

    is_symlink = attr.ib(
        default=False,
        metadata=dict(doc='True for symlink.')
    )


@attr.attributes
class Layer(ToDictMixin, ConfigMixin):
    """
    A layer object represents a slice of a root filesyetem.
    """
    format_version = '1.0'

    layer_location = attr.attrib(
        default=None,
        metadata=dict(doc='The base directory for this layer.')
    )

    layer_sha256 = attr.attrib(
        default=None,
        metadata=dict(doc='The SHA256 digest of the layer.tar file for this layer.')
    )

    layer_size = attr.attrib(
        default=attr.Factory(int),
        metadata=dict(doc='Size in byte of the layer.tar archive')
    )

    layer_id = attr.attrib(
        default=None,
        metadata=dict(doc='The id for this layer. aka. its directory')
    )

    created_by = attr.attrib(
        default=None,
        metadata=dict(doc='The command for this layer.')
    )

    is_empty_layer = attr.attrib(
        default=False,
        metadata=dict(doc='True if this is an empty layer. An empty layer has no tarball.')
    )

    parent_id = attr.attrib(
        default=None,
        metadata=dict(doc='parent layer id. LEGACY V10 format.')
    )

    extracted_to_location = attr.attrib(
        default=None,
        metadata=dict(doc='The directory where this layer has been extracted to '
            'as a plain rootfs.')
    )

    def __attrs_post_init__(self, *args, **kwargs):
        if self.layer_location and not self.layer_id:
            # reconstruct that id from the path
            self.layer_id = path.basename(path.dirname(self.layer_location))

    def extract(self, target_dir, use_layer_id=True, force_extract=False):
        """
        Extract layer tarball to `target_dir` directory.
        If `use_layer_id` is True, extract in a dir named ``target_dir/layer_id/``
        Cache the location where this layer was last extracted in the
        ``self.extracted_to_location`` attribute.

        If `force_extract` is False, do not extract if self.extracted_to_location
        already exists
        """
        if use_layer_id:
            self.extracted_to_location = path.join(target_dir, self.layer_id)

        if force_extract or not os.path.exists(self.extracted_to_location):
            utils.extract_tar(self.layer_location, self.extracted_to_location)

    def get_resources(self, with_dir=False):
        """
        Yield a Resource for each file in that layer.
        """
        if not self.extracted_to_location:
            raise Exception('The layer has not been extracted.')

        for top, dirs, files in os.walk(self.extracted_to_location):
            for f in files:
                location = os.path.join(top, f)
                path = location.replace(self.extracted_to_location, '')
                layer_path = os.path.join(self.layer_id, path.lstrip('/'))
                yield Resource(
                    location=location,
                    path=path,
                    layer_path=layer_path,
                    is_file=True,
                    is_symlink=os.path.islink(location),
                )
            if with_dir:
                for d in dirs:
                    location = os.path.join(top, d)
                    path = location.replace(self.extracted_to_location, '')
                    layer_path = os.path.join(self.layer_id, path.lstrip('/'))
                    yield Resource(
                        location=location,
                        path=path,
                        layer_path=layer_path,
                        is_file=False,
                        is_symlink=os.path.islink(location),
                    )

    def get_installed_packages(self, packages_getter):
        """
        Yield tuples of (package_url, package) for installed packages found in
        that layer using the `packages_getter` function or callable.

        The `packages_getter()` function should:

        - accept a first argument string that is the root directory of
          filesystem of this the layer

        - yield tuples of (package_url, package) where package_url is a
          package_url string that uniquely identifies the package  and `package`
          is some object that represents the package (typically a scancode-
          toolkit packagedcode.models.Package class or some nested mapping with
          the same structure).
        """
        return packages_getter(self.extracted_to_location)

    @staticmethod
    def from_layer_tarball(location, layer_sha256):
        """
        Return a Layer object built from a layer tarball at `location`.
        Raise an exception on errors.
        """
        if not location or not path.isfile(location):
            return

        layer = Layer(
            layer_sha256=sha256_digest(location),
            layer_size=path.getsize(location),
            layer_location=path.dirname(location),
            is_empty_layer=False,
        )
        return layer

    @classmethod
    def from_layer_dir(cls, location):
        """
        DEPRECATED:
        Return a Layer object built from layer metadata in the layer_dir.
        Raise an exception on errors.
        Legacy for v1-style layouts only.
        """
        if not location or not path.isdir(location):
            return

        # infer from the directory
        layer_id = path.basename(location)

        files = os.listdir(location)
        assert files
        logger_debug('from_dir: Layer files: ', files, 'layer_dir: ', location)

        # check that all the files we expect to be in the layer dir are present.
        assert LAYER_VERSION_FILE in files, ('Missing layer VERSION for: {}'.format(location))
        assert LAYER_JSON_FILE in files, ('Missing layer json for: {}'.format(location))
        assert LAYER_TAR_FILE in files, ('Missing layer.tar for: {}'.format(location))

        layer_format_version_file = path.join(location, LAYER_VERSION_FILE)
        supported_format_version = cls.format_version
        with open(layer_format_version_file) as lv:
            layer_format_version = lv.read().strip()
            assert supported_format_version == layer_format_version, (
                'Unknown layer format version: {layer_format_version} '
                'in: {layer_format_version_file}. '
                'Supported version: {supported_format_version}'.format(**locals())
            )

        # Note: it is possible to have an EMPTY layer.tar that is a link to another
        # non-empty layer.tar. This is not handled for now.
        layer_tar = path.join(location, LAYER_TAR_FILE)
        layer_sha256 = sha256_digest(layer_tar)
        layer_size = path.getsize(layer_tar)

        # load data
        with open(path.join(location, LAYER_JSON_FILE)) as layer_json:
            layer_data = json.load(layer_json)

        # make some basic checks
        assert layer_id == layer_data['id']

        is_empty_layer = layer_data.get('config', {}).get('empty_layer')

        config_data = ConfigMixin.from_config_data(layer_data)

        layer = Layer(
            layer_sha256=layer_sha256,
            layer_id=layer_id,
            layer_size=layer_size,
            layer_location=location,
            is_empty_layer=is_empty_layer,
            **config_data
        )
        return layer
