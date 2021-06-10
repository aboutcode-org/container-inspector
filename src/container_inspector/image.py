#
# Copyright (c) nexB Inc. and others. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
# See http://www.apache.org/licenses/LICENSE-2.0 for the license text.
# See https://github.com/nexB/container-inspector for support or download.
# See https://aboutcode.org for more information about nexB OSS projects.
#

import logging
import os

import attr

from commoncode.fileutils import delete

from container_inspector import MANIFEST_JSON_FILE

from container_inspector.distro import Distro
from container_inspector import utils
from container_inspector.utils import as_bare_id
from container_inspector.utils import load_json
from container_inspector.utils import sha256_digest

TRACE = False
logger = logging.getLogger(__name__)
if TRACE:
    import sys
    logging.basicConfig(level=logging.DEBUG, stream=sys.stdout)
    logger.setLevel(logging.DEBUG)

"""
Objects to handle Docker and OCI images and Layers.


Supported formats:
- docker v1.1 and v1.2
- OCI (not yet)

The objects supported here are:
- Image: which is a Docker image that contains manifest and layers
  - Layer: which is rootfs slice or "diff"
    - Resource: which repesent a file or directory inside a Layer

The Docker Image Specifications are at:
- https://github.com/moby/moby/blob/master/image/spec/v1.md (no longer supported)
- https://github.com/moby/moby/blob/master/image/spec/v1.1.md
- https://github.com/moby/moby/blob/master/image/spec/v1.2.md

The OCI specs:
- https://github.com/opencontainers/image-spec/blob/master/spec.md
- https://github.com/opencontainers/image-spec/blob/master/image-layout.md
- https://github.com/opencontainers/image-spec/blob/master/layer.md#whiteouts

The Docker Manifest Specifications are at:
- https://github.com/docker/distribution/blob/master/docs/spec/deprecated-schema-v1.md
- https://github.com/docker/distribution/blob/master/docs/spec/manifest-v2-1.md
- https://github.com/docker/distribution/blob/master/docs/spec/manifest-v2-2.md

The OCI specs:
- https://github.com/opencontainers/image-spec/blob/master/manifest.md
"""


class ToDictMixin(object):
    """
    A mixin to add an to_dict() method to an attr-based class.
    """

    def to_dict(self, exclude_fields=()):
        if exclude_fields:
            filt = lambda attr, value: attr.name not in exclude_fields
        else:
            filt = lambda attr, value: True
        return attr.asdict(self, filter=filt)


def flatten_images_data(images):
    """
    Yield mapping for each layer of each image of an `images` list of Image.
    This is a flat data structure for CSV and tabular output.
    """

    for img in images:
        base_data = dict(
            image_extracted_location=img.extracted_location,
            image_archive_location=img.archive_location,
            image_id=img.image_id,
            image_tags=','.join(img.tags),
        )
        for layer in img.layers:
            layer_data = dict(base_data)
            layer_data['is_empty_layer'] = layer.is_empty_layer
            layer_data['layer_id'] = layer.layer_id
            layer_data['layer_sha256'] = layer.sha256
            layer_data['author'] = layer.author
            layer_data['created_by'] = layer.created_by
            layer_data['created'] = layer.created
            layer_data['comment'] = layer.comment
            layer_data['layer_extracted_location'] = layer.extracted_location
            layer_data['layer_archive_location'] = layer.archive_location
            yield layer_data


@attr.attributes
class ConfigMixin(object):
    """
    Configuration data. Shared definition as found in a layer json file and an
    image config json file.
    """
    docker_version = attr.attrib(
        default=None,
        metadata=dict(doc='The docker version.')
    )

    os = attr.attrib(
        default=None,
        metadata=dict(doc='Operating system.')
    )

    os_version = attr.attrib(
        default=None,
        metadata=dict(doc='Operating system version.')
    )

    architecture = attr.attrib(
        default=None,
        metadata=dict(doc='Architecture.')
    )

    variant = attr.attrib(
        default=None,
        metadata=dict(doc='Architecture variant.')
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
        metadata=dict(doc=
            'List of labels for this layer merged from the '
            'original config and container_config.'
        )
    )

    @classmethod
    def from_config_data(cls, data):
        """
        Return a mapping of `data` suitable to use as kwargs from a layer or an
        image config data mapping.
        """
        data = utils.lower_keys(data)

        config = data.get('config', {})
        container_config = data.get('container_config', {})

        return dict(
            docker_version=data.get('docker_version'),
            os=data.get('os'),
            os_version=data.get('os.version'),
            architecture=data.get('architecture'),
            variant=data.get('variant'),
            created=data.get('created'),
            author=config.get('author'),
            comment=data.get('comment'),
            labels=utils.get_labels(config, container_config),
        )


@attr.attributes
class ArchiveMixin:
    """
    An object such as an Image or Layer that has an extracted_location that is a
    directory where files exists extracted and an archive_location which is the
    location of the original tarball archive for this object.
    """

    extracted_location = attr.attrib(
        default=None,
        metadata=dict(doc=
            'Absolute directory location where this Archive is extracted.'
        )
    )

    archive_location = attr.attrib(
        default=None,
        metadata=dict(doc=
            'Absolute directory location of this Archive original archive.'
            'May be empty if this was created from an extracted_location directory.'
        )
    )

    sha256 = attr.attrib(
        default=None,
        metadata=dict(doc='SHA256 digest of this archive (if there is an archive.)')
    )

    def set_sha256(self):
        """
        Compute and set the sha256 attribute.
        Set to None if ``archive_location`` is not set for this object.
        """
        if self.archive_location and not self.sha256:
            self.sha256 = sha256_digest(self.archive_location)


@attr.attributes
class Image(ArchiveMixin, ConfigMixin, ToDictMixin):
    """
    A container image with pointers to its layers.
    Image objects can be created from these inputs:
    - an image tarball in docker format (e.g. "docker save").
    - a directory that contains an extracted image tarball in these layouts.

    OCI format is not yet supported.
    """

    image_format = attr.attrib(
        default=None,
        metadata=dict(doc=
            'Format of this this image as of one of: "docker" or "oci".'
        )
    )

    image_id = attr.attrib(
        default=None,
        metadata=dict(doc=
            'Id for this image. '
            'This is the base name of the config json file '
            'and is the same as a non-prefixed digest for the config JSON file.'
        )
    )

    config_digest = attr.attrib(
        default=None,
        metadata=dict(doc=
            'Digest of the config JSON file for this image. '
            'This is supposed to be the same as the id. '
        )
    )

    tags = attr.attrib(
        default=attr.Factory(list),
        metadata=dict(doc=
            'List of tags for this image".'
        )
    )
    distro = attr.attrib(
        default=None,
        metadata=dict(doc='Distro object for this image.')
    )

    layers = attr.attrib(
        default=attr.Factory(list),
        metadata=dict(doc=
            'List of Layer objects ordered from bottom to top, excluding empty '
            'layers."'
        )
    )

    history = attr.attrib(
        default=attr.Factory(list),
        metadata=dict(doc='List of mapping for the layers history.')
    )

    def __attrs_post_init__(self, *args, **kwargs):
        if not self.extracted_location:
            raise TypeError('Image.extracted_location is a required argument')

        self.set_sha256()

        if not self.image_format:
            self.image_format = self.find_format(self.extracted_location)

    @property
    def top_layer(self):
        """
        Top layer for this image.
        """
        return self.layers[-1]

    @property
    def bottom_layer(self):
        """
        Bottom layer for this image.
        """
        return self.layers[0]

    def extract_layers(self, extracted_location):
        """
        Extract all layer archives to the `extracted_location` directory.
        Each layer is extracted to its own directory named after its `layer_id`.
        """
        for layer in self.layers:
            exloc = os.path.join(extracted_location, layer.layer_id)
            layer.extract(extracted_location=exloc)

    def get_layers_resources(self, with_dir=False):
        """
        Yield a Resource for each file in each layer.
        extract_layers() must have been called first.
        """
        for layer in self.layers:
            for resource in layer.get_resources(with_dir=with_dir):
                yield resource

    def get_and_set_distro(self):
        """
        Return a Distro object for this image. Raise exceptions if it cannot be
        built.
        """
        bottom_layer = self.bottom_layer
        if not bottom_layer.extracted_location:
            raise Exception('The image has not been extracted.')

        distro = Distro(
            os=self.os,
            architecture=self.architecture,
        )
        if self.os_version:
            distro.version = self.os_version

        self.distro = Distro.from_rootfs(
            location=bottom_layer.extracted_location,
            base_distro=distro,
        )

        return self.distro

    def cleanup(self):
        """
        Removed extracted layer files from self.extracted_location.
        """
        if self.extracted_location:
            delete(self.extracted_location)

        for layer in self.layers:
            layer.extracted_location = None

        self.extracted_location = None

    def squash(self, target_dir):
        """
        Extract and squash all the layers of this image as a single merged
        rootfs directory rooted in the `target_dir` directory.
        """
        from container_inspector import rootfs
        rootfs.rebuild_rootfs(self, target_dir)

    def get_installed_packages(self, packages_getter):
        """
        Yield tuples of unique (package_url, package, layer) for installed
        packages found in each of this image layers using the `packages_getter`
        function or callable. A package is reported in the layer where its
        package_url is first seen as installed. Further instances of the exact
        same package found in the installed package database in following layers
        are not reported.

        The `packages_getter()` function should:

        - accept a first argument string that is the root directory of
          filesystem of this the layer

        - yield tuples of (package_url, package) where package_url is a
          package_url string that uniquely identifies the package  and `package`
          is some object that represents the package (typically a scancode-
          toolkit packagedcode.models.Package class or some nested mapping with
          the same structure).

        An `packages_getter` function would typically query the system packages
        database (such as an RPM database or similar) to collect the list of
        installed system packages.
        """
        seen_packages = set()
        for layer in self.layers:
            for purl, package in layer.get_installed_packages(packages_getter):
                if purl in seen_packages:
                    continue
                seen_packages.add(purl)
                yield purl, package, layer

    @staticmethod
    def extract(archive_location, extracted_location):
        """
        Extract the image archive tarball at ``archive_location`` to
        ``extracted_location``.
        """
        utils.extract_tar_keeping_symlinks(
            location=archive_location,
            target_dir=extracted_location,
        )

    @staticmethod
    def get_images_from_tarball(
        archive_location,
        extracted_location,
        verify=True,
    ):
        """
        Return a list of Images found in the tarball at `archive_location` that
        will be extracted to `extracted_location`. The tarball must be in the
        format of a "docker save" command tarball.

        If `verify` is True, perform extra checks on the config data and layers
        checksums.
        """
        if TRACE: logger.debug(f'get_images_from_tarball: {archive_location} , extracting to: {extracted_location}')

        Image.extract(
            archive_location=archive_location,
            extracted_location=extracted_location,
        )

        return Image.get_images_from_dir(
            extracted_location=extracted_location,
            archive_location=archive_location,
            verify=verify,
        )

    @staticmethod
    def get_images_from_dir(
        extracted_location,
        archive_location=None,
        verify=True,
    ):
        """
        Return a list of Image found in the directory at `extracted_location`
        that can be either a in "docker save" or OCI format.

        If `verify` is True, perform extra checks on the config data and layers
        checksums.
        """
        if TRACE: logger.debug(f'get_images_from_dir: from  {extracted_location} and archive_location: {archive_location}')

        if not os.path.isdir(extracted_location):
            raise Exception(f'Not a directory: {extracted_location}')

        image_format = Image.find_format(extracted_location)

        if TRACE: logger.debug(f'get_images_from_dir: image_format: {image_format}')

        if image_format == 'docker':
            return Image.get_docker_images_from_dir(
                extracted_location=extracted_location,
                archive_location=archive_location,
                verify=verify,
        )

        if image_format == 'oci':
            return Image.get_oci_images_from_dir(
                extracted_location=extracted_location,
                archive_location=archive_location,
                verify=verify,
        )

        raise Exception(
            f'Unknown container image format {image_format} '
            f'at {extracted_location}'
        )

    @staticmethod
    def get_docker_images_from_dir(
        extracted_location,
        archive_location=None,
        verify=True,
    ):
        """
        Return a list of Image objects found in the directory at
        `extracted_location`. The directory must contain a Docker manifest.json and
        must be in the same format as a "docker save" extracted to
        `extracted_location`.

        If `verify` is True, perform extra checks on the config data and layers
        checksums.

        The "manifest.json" JSON file for format v1.1/1.2. of a saved Docker
        image contains a mapping with this shape for one or more images:

        - The `Config` field references another JSON file in same directory
          that includes the image detailed data.
        - The `RepoTags` field lists references pointing to this image.
        - The `Layers` field points to the filesystem changeset tars, e.g. the
          path to the layer.tar files as a list of paths.

        For example:

        [
            {'Config': '7043867122e704683c9eaccd7e26abcd5bc9fea413ddf.json',
             'Layers': [
                 '768d4f50f65f00831244703e57f64134771289e3de919a57/layer.tar',
                 '6a630e46a580e8b2327fc45d9d1f4734ccaeb0afaa094e0f/layer.tar',
                 ]
             'RepoTags': ['user/image:version'],
             },
            ....
        ]
        """
        if TRACE: logger.debug(f'get_docker_images_from_dir: {extracted_location}')

        if not os.path.isdir(extracted_location):
            raise Exception(f'Not a directory: {extracted_location}')

        manifest_loc = os.path.join(extracted_location, MANIFEST_JSON_FILE)
        # NOTE: we are only looking at V1.1/2 repos layout for now and not the
        # legacy v1.0.
        if not os.path.exists(manifest_loc):
            raise Exception(f'manifest.json file missing in {extracted_location}')

        manifest = load_json(manifest_loc)

        if TRACE: logger.debug(f'get_docker_images_from_dir: manifest: {manifest}')

        images = []
        for manifest_config in manifest:
            if TRACE: logger.debug(f'get_docker_images_from_dir: manifest_config: {manifest_config}')
            img = Image.from_docker_manifest_config(
                extracted_location=extracted_location,
                archive_location=archive_location,
                manifest_config=manifest_config,
                verify=verify,

            )
            if TRACE: logger.debug(f'get_docker_images_from_dir: img: {img!r}')

            images.append(img)

        return images

    @staticmethod
    def from_docker_manifest_config(
        extracted_location,
        manifest_config,
        archive_location=None,
        verify=True,
    ):
        """
        Return an Image object built from a Docker `manifest_config` data
        mapping (obtained from a manifest.json) and the `extracted_location`
        directory that contains the manifest.json and each image JSON config
        file.

        If `verify` is True, perform extra checks on the config data and layers
        checksums.
        Raise Exception on errors.

        The `manifest_config["Config"]` contains a path to JSON config file that
        is named after its SHA256 checksum and there is one such file for each
        image.

        A manifest.json `manifest_config` attribute has this shape:
          {'Config': '7043867122e704683c9eaccd7e26abcd.json',
           'Layers': [
               '768d4f50f65f00831244703e57f64134771289/layer.tar',
               '6a630e46a580e8b2327fc45d9d1f4734ccaeb0/layer.tar',
               ]
           'RepoTags': ['user/image:version'],
           }

        Each JSON config file referenced in the Config attribute such as the
        file above named: 7043867122e704683c9eaccd7e26abcd.json file has this shape:
         {
            'docker_version': '1.8.2',
            'os': 'linux',
            'architecture': 'amd64',
            'author': '<author name>',
            'created': '2016-09-30T10:16:27.109917034Z',
            'container': '1ee508bc7a35150c9e5924097a31dfb4',

            # The `image_config` and `container_config` mappings are essentially
            # similar: image_config is the runtime image_config and
            # container_config is the image_config as it existed when the
            # container was created.

            'image_config': { <some image_config k/v pairs> },
            'container_config': { <some image_config k/v pairs> },

            # `history` is an array of objects describing the history of each
            # layer. The array is ordered from bottom-most layer to top-most
            # layer, and contains also entries for empty layers.

            'history': [...],

            # Rootfs lists the "layers" in order from bottom-most to top-most
            # where each id is the sha256 of a layer.tar.

            # NOTE: Empty layer may NOT have their digest listed here, so this
            # list may not align exactly with the history list: e.g. this list
            # only has entries if "empty_layer" is not set to True for that
            # layer.

            'rootfs': {
                'diff_ids': [
                    'sha256:5f70bf18a086007016e948b04aed3b82103a3',
                    'sha256:2436bc321ced91d2f3052a98ff886a2feed07',
                    'sha256:cd141a5beb0ec83004893dfea6ea8508c6d09',]
                'type': u'layers'
            }
         }
        """
        if TRACE: logger.debug(f'from_docker_manifest_config: manifest_config: {manifest_config!r}')

        manifest_config = utils.lower_keys(manifest_config)

        config_file = manifest_config.get('config') or ''
        config_file_loc = os.path.join(extracted_location, config_file)
        if not os.path.exists(config_file_loc):
            raise Exception(
                f'Invalid configuration. Missing Config file: {config_file_loc}')

        image_id, _ = os.path.splitext(os.path.basename(config_file_loc))
        config_digest = sha256_digest(config_file_loc)
        if verify and image_id != as_bare_id(config_digest):
            raise Exception(
                f'Image config {config_file_loc} SHA256:{image_id} is not '
                f'consistent with actual computed value SHA256: {config_digest}'
            )

        config_digest = f'sha256:{image_id}'

        # "Layers" can be either a path to the layer.tar:
        # "d388bee71bbf28f77042d89b353bacd14506227/layer.tar"

        # Or with a linked format (e.g. skopeo) where the layer.tar above is a
        # link to a tarball named after its sha256 and located at the root
        # 5f70bf18a086007016e948b04aed3b82103a36be.tar

        layer_paths = manifest_config.get('layers') or []
        layers_archive_locs = [
            os.path.join(extracted_location, lp)
            for lp in layer_paths
        ]

        tags = manifest_config.get('repotags') or []

        image_config = utils.lower_keys(load_json(config_file_loc))
        rootfs = image_config['rootfs']
        rt = rootfs['type']
        if rt != 'layers':
            raise Exception(
                f'Unknown type for image rootfs: expecting "layers" and '
                f'not {rt} in {config_file_loc}'
            )

        # TODO: add support for empty tarball as this may not work if there is a
        # diff for an empty layer with a digest for some EMPTY content e.g.
        # e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855

        layers_sha256s = [as_bare_id(lsha256) for lsha256 in rootfs['diff_ids']]
        layer_arch_locs_and_sha256s = zip(layers_archive_locs, layers_sha256s)

        layers = []
        for layer_archive_loc, layer_sha256 in layer_arch_locs_and_sha256s:

            if verify:
                on_disk_layer_sha256 = sha256_digest(layer_archive_loc)
                if layer_sha256 != on_disk_layer_sha256:
                    raise Exception(
                        f'Layer archive: SHA256:{on_disk_layer_sha256}\n at '
                        f'{layer_archive_loc} does not match \n'
                        f'its "diff_id": SHA256:{layer_sha256}'
                    )

            layers.append(Layer(
                archive_location=layer_archive_loc,
                sha256=layer_sha256,
            ))

        history = image_config.get('history') or {}
        assign_history_to_layers(history, layers)

        img = Image(
            image_format='docker',
            extracted_location=extracted_location,
            archive_location=archive_location,
            image_id=image_id,
            layers=layers,
            config_digest=config_digest,
            history=history,
            tags=tags,
            **ConfigMixin.from_config_data(image_config)
        )

        return img

    @staticmethod
    def find_format(extracted_location):
        """
        Rreturn the format of the image at ``extracted_location`` as one of:
        - docker (which is for the docker v2 format)
        - oci (which is for the OCI format)
        """
        clue_files_by_image_format = {
            'docker': ('manifest.json',),
            'oci': ('blobs', 'index.json', 'oci-layout',)
         }

        files = os.listdir(extracted_location)
        for image_format, clues in clue_files_by_image_format.items():
            if all(c in files for c in clues):
                return image_format

    @staticmethod
    def get_oci_images_from_dir(
        extracted_location,
        archive_location=None,
        verify=True,
    ):
        """
        Return a list of Images created from OCI images found at
        `extracted_location` that is a directory where an OCI image tarball has
        been extracted.

        index.json
        oci-layout
        blobs/sha256
            # at least three files, one being a tarball. Each named after their sha256
            /17dc2d6ad713655494f3a90a06a5479c62108
            /cdce9ebeb6e8364afeac430fe7a886ca89a90
            /540db60ca9383eac9e418f78490994d0af424

        index.json:

        {
          "schemaVersion": 2,
          "manifests": [
            {
              "mediaType": "application/vnd.oci.image.manifest.v1+json",
              "digest": "sha256:17dc2d6ad713655494f3a90",
              "size": 348
            }
          ]
        }
        which points to a blob:

        Then in 17dc2d6ad713655494f3a90a06a5479c62108 which is JSON
        and points to a manifest and a layers
        {
          "schemaVersion": 2,
          "config": {
            "mediaType": "application/vnd.oci.image.config.v1+json",
            "digest": "sha256:cdce9ebeb6e8364afeac430fe7",
            "size": 585
          },
          "layers": [
            {
              "mediaType": "application/vnd.oci.image.layer.v1.tar+gzip",
              "digest": "sha256:540db60ca9383eac9e418f78",
              "size": 2811969
            }
          ]
        }
        And this cdce9ebeb6e8364afeac430fe
        is a JSON with essentially the same image_config contenet as the Docker format:

        {
          "created": "2021-04-14T19:19:39.643236135Z",
          "architecture": "amd64",
          "os": "linux",
          "config": {
            "Env": [
              "PATH=/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin"
            ],
            "Cmd": [
              "/bin/sh"
            ]
          },
          "rootfs": {
            "type": "layers",
            "diff_ids": [
              "sha256:b2d5eeeaba3a22b9b8aa97261957974a6"
            ]
          },
          "history": [
            {
              "created": "2021-04-14T19:19:39.267885491Z",
              "created_by": "/bin/sh -c #(nop) ADD file:8ec69d882e7f29f0652 in / "
            },
            {
              "created": "2021-04-14T19:19:39.643236135Z",
              "created_by": "/bin/sh -c #(nop)  CMD [\"/bin/sh\"]",
              "empty_layer": true
            }
          ]
        }
        """
        index_loc = os.path.join(extracted_location, 'index.json')
        index = load_json(index_loc)
        index = utils.lower_keys(index)
        if index['schemaversion'] != 2:
            raise Exception(
                f'Unsupported OCI index schema version in {index_loc}. '
                'Only 2 is supported.'
            )

        images = []
        for manifest_data in index['manifests']:
            mediatype = manifest_data['mediatype']
            if mediatype != 'application/vnd.oci.image.manifest.v1+json':
                raise Exception(
                    f'Unsupported OCI index media type {mediatype} in {index_loc}.'
                )
            manifest_digest = manifest_data['digest']
            manifest_sha256 = as_bare_id(manifest_digest)
            manifest_loc = get_oci_blob(
                extracted_location, manifest_sha256, verify=verify)
            manifest = load_json(manifest_loc)

            config_digest = manifest['config']['digest']
            config_sha256 = as_bare_id(config_digest)
            config_loc = get_oci_blob(
                extracted_location, config_sha256, verify=verify)
            config = load_json(config_loc)

            layers = []
            for layer in manifest['layers']:
                layer_digest = layer['digest']
                layer_sha256 = as_bare_id(layer_digest)
                layer_arch_loc = get_oci_blob(
                    extracted_location, layer_sha256, verify=verify)
                layers.append(Layer(
                    archive_location=layer_arch_loc,
                    sha256=layer_sha256,
                ))

            history = config.get('history') or {}
            assign_history_to_layers(history, layers)

            images.append(Image(
                image_format='oci',
                extracted_location=extracted_location,
                archive_location=archive_location,
                image_id=config_sha256,
                layers=layers,
                config_digest=config_digest,
                history=history,
                **ConfigMixin.from_config_data(config)
            ))

        return images


def get_oci_blob(extracted_location, sha256, verify=True):
        loc = os.path.join(extracted_location, 'blobs', 'sha256', sha256)
        if not os.path.exists(loc):
            raise Exception(f'Missing OCI image file {loc}')
        if verify:
            on_disk_sha256 = sha256_digest(loc)
            if sha256 != on_disk_sha256:
                raise Exception(
                    f'For {loc} on disk SHA256:{on_disk_sha256} does not '
                    f'match its expected index SHA256:{sha256}'
                )
        return loc


def assign_history_to_layers(history, layers):
    """
    Given a list of history data mappings and a list of Layer objects, attempt
    to assign history-related fields to each Layer if possible

    `history` is an array of objects describing the history of each
    layer. The array is ordered from bottom-most layer to top-most
    layer, and contains also entries for empty layers.

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
    History spec is at
    https://github.com/opencontainers/image-spec/blob/79b036d80240ae530a8de15e1d21c7ab9292c693/config.md
    """
    if not history:
        return

    non_empty_history = [h for h in history if not h.get('empty_layer', False)]
    non_empty_layers = [l for l in layers if not l.is_empty_layer]

    if len(non_empty_history) != len(non_empty_layers):
        # we cannot align history with layers if we do not have the same numbers
        # of entries
        # TODO: raise some warning?
        return

    fields = 'author', 'created', 'created_by', 'comment'

    for hist, layer in zip(non_empty_history, non_empty_layers):
        hist = utils.lower_keys(hist)
        for field in fields:
            value = hist.get(field)
            if value:
                setattr(layer, field, value)


@attr.attributes
class Resource(ToDictMixin):
    path = attr.attrib(
        default=None,
        metadata=dict(doc='Rootfs-relative path for this Resource.')
    )

    layer_path = attr.attrib(
        default=None,
        metadata=dict(doc=
            'Rootfs-relative path with the addition of the layer id as a prefix.'
        )
    )

    location = attr.attrib(
        default=None,
        metadata=dict(doc='Absolute location of this Resource.')
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
class Layer(ArchiveMixin, ConfigMixin, ToDictMixin):
    """
    A layer object represents a slice of a root filesystem in a container image.
    """

    layer_id = attr.attrib(
        default=None,
        metadata=dict(doc=
            'Id for this layer which must be set to the SHA256 of its archive.'
        )
    )

    size = attr.attrib(
        default=0,
        metadata=dict(doc='Size in byte of the layer archive')
    )

    is_empty_layer = attr.attrib(
        default=False,
        metadata=dict(doc=
            'True if this is an empty layer. An empty layer has no content.'
        )
    )

    author = attr.attrib(
        default=None,
        metadata=dict(doc='Author of this layer.')
    )

    created = attr.attrib(
        default=None,
        metadata=dict(doc='Date/timestamp for when this layer was created.')
    )

    created_by = attr.attrib(
        default=None,
        metadata=dict(doc='Command used to create this layer.')
    )

    comment = attr.attrib(
        default=None,
        metadata=dict(doc='A comment for this layer.')
    )

    def __attrs_post_init__(self, *args, **kwargs):
        if not self.archive_location:
            raise TypeError('Layer.archive_location is a required argument')

        self.set_sha256()
        self.layer_id = self.sha256

        if not self.size:
            self.size = os.path.getsize(self.archive_location)

    def extract(self, extracted_location):
        """
        Extract this layer archive in the `extracted_location` directory and set
        this Layer ``extracted_location`` attribute to ``extracted_location``.
        """
        self.extracted_location = extracted_location
        utils.extract_tar(
            location=self.archive_location,
            target_dir=extracted_location,
        )

    def get_resources(self, with_dir=False, walker=os.walk):
        """
        Yield a Resource for each file in this layer, omit directories if
        ``with_dir`` is False.
        """
        if not self.extracted_location:
            raise Exception('The layer has not been extracted.')

        def build_resource(_top, _name, _is_file):
            _loc = os.path.join(top, _name)
            _path = _loc.replace(self.extracted_location, '')
            _layer_path = os.path.join(self.layer_id, _path.lstrip('/'))

            return Resource(
                location=_loc,
                path=_path,
                layer_path=_layer_path,
                is_file=_is_file,
                is_symlink=os.path.islink(_loc),
            )

        for top, dirs, files in walker(self.extracted_location):
            for f in files:
                yield build_resource(top, f, _is_file=True)
            if with_dir:
                for d in dirs:
                    yield build_resource(top, d, _is_file=True)

    def get_installed_packages(self, packages_getter):
        """
        Yield tuples of (package_url, package) for installed system packages
        found in this layer using the `packages_getter` function or callable.

        The `packages_getter()` function or callable should:

        - accept a first argument string that is the root directory of
          filesystem of this the layer

        - yield tuples of (package_url, package) where package_url is a
          package_url string that uniquely identifies the package  and `package`
          is some object that represents the package (typically a scancode-
          toolkit packagedcode.models.Package class or some nested mapping with
          the same structure).
        """
        return packages_getter(self.extracted_location)
