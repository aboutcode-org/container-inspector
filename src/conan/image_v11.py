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

from collections import defaultdict
from collections import OrderedDict
from functools import partial
import json
import logging
from os.path import exists
from os.path import isdir
from os.path import join
import sys

import attr

from commoncode import filetype
from commoncode import fileutils
from commoncode.fileutils import file_base_name
from commoncode.fileutils import parent_directory

from conan import LAYER_JSON_FILE
from conan import LAYER_TAR_FILE
from conan import LAYER_VERSION_FILE
from conan import MANIFEST_JSON_FILE

from conan.utils import as_bare_id
from conan.utils import get_command
from conan.utils import listdir
from conan.utils import load_json
from conan.utils import merge_update_mappings
from conan.utils import sha256_digest


logger = logging.getLogger(__name__)
# un-comment these lines to enable logging
# logging.basicConfig(level=logging.DEBUG, stream=sys.stdout)
# logger.setLevel(logging.DEBUG)


def logger_debug(*args):
    return logger.debug(' '.join(isinstance(a, basestring) and a or repr(a) for a in args))


"""
Objects to handle Docker repositories, images and layers data in v1.1 and v1.2 format.
"""

defaultdict_list = partial(defaultdict, list)


class AsDictMixin(object):
    """
    A mixin to add an as_dict() method to an attr-based class.
    """
    def as_dict(self):
        return attr.asdict(self, dict_factory=OrderedDict)


@attr.attributes
class Registry(AsDictMixin):
    """
    A collection of several Repositories (that may or may not be related).
    """
    repositories = attr.attrib(
        default=attr.Factory(dict),
        metadata=dict(doc='a mapping of repo_dir->Repository object')
    )

    def unique_layers(self):
        """
        Yield a tuple of (repo_dir, layer object) for every unique layer in this registry.
        """
        seen = set()
        for repo_dir, repo in self.repositories.iteritems():
            for layer_id, layer in repo.layers_by_id.iteritems():
                if layer_id in seen:
                    continue
                seen.add(layer_id)
                yield repo_dir, layer

    def unique_images(self):
        """
        Yield a tuple of (repo_dir, image object) for every unique images in this registry.
        """
        seen = set()
        for repo_dir, repo in self.repositories.iteritems():

            for image_id, image in repo.images_by_id.iteritems():
                if image_id in seen:
                    continue
                seen.add(image_id)
                yield repo_dir, image

    def clustered_layers(self):
        """
        Return a list of layer lists in this registry where each sublist is clustered
        together with this heuristics to join layers in a cluster:

        - identical layers are joined in a cluster.
        - layers with reasonably similar sizes and the same command are joined in a
          cluster, eventually the same cluster as identical layers.
        """
        raise NotImplementedError

    def layer_images(self):
        """
        Return a mapping of unique layer_id-> [list of image ids where this layer is used]
        """
        raise NotImplementedError

    def populate(self, base_dir):
        """
        Collect the `base_dir` for image repositories.
        """
        for fil in fileutils.file_iter(base_dir):
            # FIXME: we are only looking at V11 repos for now.
            fn = fileutils.file_name(fil)
            if not fn == MANIFEST_JSON_FILE:
                continue
            rd = parent_directory(fil)
            repo = Repository()
            repo.load_manifest(rd)
            logger_debug('populate: path: %(fn)r' % locals())
            self.repositories[rd] = repo

    def repos(self):
        return self.repositories

    def flatten(self):
        """
        Yeild records for each layer of each image of each repository of this registry.
        This is a flat data structure for csv output.
        """
        for repo_dir, repo in self.repositories.items():
            for image in repo.images_by_id.values():
                base_data = OrderedDict([
                    ('repo_dir', repo_dir),
                    ('image_id', image.image_id),
                    ('image_tags', ','.join(image.tags)),
                ])
                for layer in image.layers:
                    layer_data = OrderedDict(base_data)
                    layer_data['author'] = layer.author
                    layer_data['created_by'] = layer.created_by
                    layer_data['layer_id'] = layer.layer_id
                    layer_data['layer_digest'] = layer.layer_digest
                    layer_data['empty_layer'] = layer.empty_layer
                    if layer.layer_id:
                        ld = join(repo_dir, layer.layer_id)
                    else:
                        ld = None
                    layer_data['layer_dir'] = ld
                    yield layer_data


@attr.attributes
class Repository(AsDictMixin):
    """
    A collection of several related images stored in a common directory, sharing
    layers.
    """
    format_versions = ('1.1', '1.2',)

    layers_by_id = attr.attrib(
        default=attr.Factory(dict),
        metadata=dict(doc='a mapping of (layer_id-> layer object) from bottom to top')
    )

    images_by_id = attr.attrib(
        default=attr.Factory(dict),
        metadata=dict(doc='a mapping of image_id-> image object')
    )

    image_id_by_tags = attr.attrib(
        default=attr.Factory(defaultdict_list),
        metadata=dict(doc='mapping of name:tag -> image id for images in this repository')
    )

    def load_manifest(self, repo_dir):
        """
        Load this repository from a "manifest.json" JSON file for format v1.1/1.2.

        This file is a mapping with this shape:

        - The `Config` field references another JSON file in the tar or repo which
          includes the image data for this image.

        - The `RepoTags` field lists references pointing to this image.

        - The `Layers` field points to the filesystem changeset tars, e.g. the path
         to the layer.tar files as a list ordered from bottom to top layer.

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
        manifest_file = join(repo_dir, MANIFEST_JSON_FILE)
        manifest = load_json(manifest_file)

        for image_config in manifest:
            config_file = image_config.get('Config')

            config_file = join(repo_dir, config_file)
            if not exists(config_file):
                # FIXME: orphaned manifest entry
                image_id = file_base_name(config_file)
                image = Image(image_id=image_id)
                assert image.image_id not in self.images_by_id
                self.images_by_id[image.image_id] = image
                continue

            image = Image.load_image_config(config_file)
            assert image.image_id not in self.images_by_id
            self.images_by_id[image.image_id] = image

            image.parent_digest = image_config.get('Parent')

            image.tags = image_config.get('RepoTags') or []
            for tag in image.tags:
                self.image_id_by_tags[tag] = image.image_id

            image_layers_by_digest = {l.layer_digest: l for l in image.layers}

            layer_paths = image_config.get('Layers') or []
            layers = OrderedDict()
            for lp in layer_paths:
                layer_dir = fileutils.parent_directory(lp).strip('/')
                layer_id = layer_dir
                layer_dir = join(repo_dir, layer_dir)
                layer = Layer.load_layer(layer_dir)
                layer_digest = sha256_digest(join(repo_dir, lp))
                if layer.layer_digest:
                    assert layer.layer_digest == layer_digest
                layers[layer_id] = layer
                self.layers_by_id[layer_id] = layer
                image_layer = image_layers_by_digest.get(layer_digest)
                if image_layer:
                    image_layer.layer_id = layer_id
            


            # the last one is the top one
            image.top_layer_id = layer_id
            image.top_layer_digest = layer_digest

    @classmethod
    def load_repositories(cls, repositories_file):
        """
        Yield images loaded from a legacy "repositories" JSON file for format v1.0.

        This file is a mapping with this shape:
        {
            "username/imagename": { "version1": "top layer id", "version2" : "top layer id", }
        }

        For example:
        {
         "me/test_image_tar":      {"1.0":"de331f94dc3592a39e495432d39ca14ed0cf04a6861c1e7714ff410e8a0225b4"},
         "she/image_from_scratch": {"1.0":"a699c18e2119e668e5f1264e97559af65d2111ac0790b6832efeb450fc5193fc"},
         "you/secondimage":        {"1.2":"1466996a39f8d2af81b92fad37ef15c04fb2ca64b43945a00f6f5943913f6b96"}
        }

        The top layer id is the name of the layer.tar parent dir and not a digest in
        this legacy format.
        """
        repositories = load_json(repositories_file)
        for image_name, versions in repositories.items():
            for version, top_layer_id in versions:
                tag = ':'.join([image_name, version])
                yield tag, top_layer_id


"""
 digestSHA256GzippedEmptyTar is the canonical sha256 digest of
// gzippedEmptyTar
const digestSHA256GzippedEmptyTar = digest.Digest("sha256:a3ed95caeb02ffe68cdd9fd84406680ae93d633cb16422d00e8a7c22955b46d4")
"""

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

    container = attr.attrib(
        default=None,
        metadata=dict(doc='Id for this container. ???')
    )

    comment = attr.attrib(
        default=None,
        metadata=dict(doc='comment')
    )

    config = attr.attrib(
        default=attr.Factory(OrderedDict),
        metadata=dict(doc='Mapping of config data merged from the original config and container_config.')
    )


@attr.attributes
class Image(AsDictMixin, ConfigMixin):
    """
    A container image with pointers to its layers.
    """

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

    top_layer_id = attr.attrib(
        default=None,
        metadata=dict(doc='The top layer id for this image.')
    )

    top_layer_digest = attr.attrib(
        default=None,
        metadata=dict(doc='The top layer digest for this image.')
    )

    layer_digests = attr.attrib(
        default=attr.Factory(list),
        metadata=dict(doc='A list of layer digests from bottom to top.')
    )

    layers = attr.attrib(
        default=attr.Factory(list),
        metadata=dict(doc='A list of layer objects from bottom to top.')
    )

    tags = attr.attrib(
        default=attr.Factory(list),
        metadata=dict(doc='List of tags for this image as strings of "user/name:version".')
    )


    @classmethod
    def load_image_config(cls, config_file, verbose=True):
        """
        Return an Image object built from the image_config JSON file at location.

        Each Config JSON file for each image has this shape:
        {
            'docker_version': '1.8.2',
            'os': 'linux',
            'architecture': 'amd64',
            'author': '<author name>',
            'created': '2016-09-30T10:16:27.109917034Z',
            'container': '1ee508bc7a35150c9e5924097a31dfb4b6b2ca1260deb6fd14cb03c53764e40b',
            # these two mappings are essentially similar: image_config is the runtime image_config
            # and container_config is the image_config as it existed when the container was created.
            'image_config': { <some image_config k/v pairs> },
            'container_config': { <some image_config k/v pairs> },
            # array of objects describing the history of each layer.
            # The array is ordered from bottom-most layer to top-most layer.

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
                 'created_by': '/bin/sh -c #(nop) ADD file:eab3c29917290b056db08167d3a9f769c4b4ce46403be2fad083bc2535fb4d03 in /'
                },
            ]
            # this is in order from bottom-most to top-most
            # each id is the sha256 of a layer.tar
            # NOTE: Empty layer may NOT have their digest listed here, so this list
            # may not align exactly with the history list:
            # e.g. this list only has entries if "empty_layer" is not set to True for that layer.
            'rootfs': {
                'diff_ids': ['sha256:5f70bf18a086007016e948b04aed3b82103a36bea41755b6cddfaf10ace3c6ef',
                             'sha256:2436bc321ced91d2f3052a98ff886a2feed0788eb524b2afeb48099d084c33f5',
                             'sha256:cd141a5beb0ec83004893dfea6ea8508c6d09a0634593c3f35c0d433898c9322',]
                'type': u'layers'
            }
        }
        """

        image_id = fileutils.file_base_name(config_file)
        config_digest = sha256_digest(config_file)
        if image_id != as_bare_id(config_digest):
            print('WARNING: image config digest is not consistent.')
            config_digest = 'sha256' + image_id

        image_config = load_json(config_file)

        # merge "configs"
        ccnf = image_config.pop('container_config', {})
        cnf = image_config.pop('config', {})
        config, warns = merge_configs(ccnf, cnf)

        if warns and verbose:
            print('Warning when loading: %(config_file)r' % locals())

            for w in warns:
                print(w)

        rootfs = image_config.pop('rootfs')
        # we only support this for now
        assert rootfs['type'] == 'layers'
        digests = rootfs['diff_ids']
        digests_it = iter(digests)

        # FIXME: this may not work if there is a diff for an empty layer with a
        # digest for some EMPTY content e.g. e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855

        # update layer data with digest(e.g align history and diff digests, skipping empty layers that have no digest)
        layers = image_config.pop('history')
        for lay in layers:
            if lay.get('empty_layer'):
                continue
            lay['layer_digest'] = next(digests_it)

        remaining = list(digests_it)
        assert not remaining

        
        layers = [Layer(**l) for l in layers]
        image_data = dict (
            image_id=image_id,
            layers=layers,
            config_digest=config_digest,
            top_layer_digest=layers[-1].layer_digest,
            top_layer_id=layers[-1].layer_id,
            #config=config,
        )
        image_data.update(image_config)

        image = Image(**image_data)

        return image


def merge_configs(container_config, config):
    """
    Merge and return a new mapping from the container_config and config Docker
    mappings. These two mappings have the same shape but may not contain the same
    data exactly: we need to keep only one of these.

    We give priority to the container_config which represent the configuration
    (including the command) used to create a layer originally. These config mappings
    are present in a layer "json" file (legacy v1.0) and in the image config json
    file (v1.1/v1.2).
    """
    return merge_update_mappings(container_config, config, mapping=OrderedDict)


@attr.attributes
class LayerConfigMixin(ConfigMixin):
    """
    Configuration data as found in a layer json file.
    """
    created_by = attr.attrib(
        default=None,
        metadata=dict(doc='The command used to create this layer. New in V11 format.')
    )

    empty_layer = attr.attrib(
        default=False,
        metadata=dict(doc='True if this is an empty layer. New in V11 format.')
    )

    parent = attr.attrib(
        default=None,
        metadata=dict(doc='parent layer id. LEGACY V10 format.')
    )


@attr.attributes
class Layer(AsDictMixin, LayerConfigMixin):
    """
    A layer object represents a slice of a root filesyetem.
    """
    format_version = '1.0'

    layer_id = attr.attrib(
        default=None,
        metadata=dict(doc='The id for this layer.')
    )

    layer_digest = attr.attrib(
        default=None,
        metadata=dict(doc='The digest of the layer.tar file for this layer.')
    )

    layer_size = attr.attrib(
        default=attr.Factory(int),
        metadata=dict(doc='Size in byte of the layer.tar archive')
    )

    command = attr.attrib(
        default=None,
        metadata=dict(doc='The command used to create this layer.')
    )

    def as_dict(self):
        ad = super(Layer, self).as_dict()
        # todo: ADD MORE COMPUTED data?
        return ad

    @classmethod
    def load_layer(cls, layer_dir, verbose=True):
        """
        Return a Layer object built from layer metadata in the layer_dir.
        Raise an exception on errors.
        """
        if not layer_dir:
            return
        # infer from the directory
        layer_id = fileutils.file_name(layer_dir)

        if not isdir(layer_dir):
            print('NOT A layer dir:', layer_dir)
            return Layer(layer_id=layer_id)
        files = listdir(layer_dir)

        assert files
        logger_debug('load_layer: Layer files: ', files, 'layer_dir: ', layer_dir)

        # check that all the files we expect to be in the layer dir are present note:
        # we ignore any other files (such as extracted tars, etc)
        if LAYER_VERSION_FILE in files:
            layer_format_version_file = join(layer_dir, LAYER_VERSION_FILE)
            supported_format_version = cls.format_version
            with open(layer_format_version_file) as lv:
                layer_format_version = lv.read().strip()
                assert supported_format_version == layer_format_version, (
                    'Unknown layer format version: %(layer_format_version)r '
                    'in: %(layer_format_version_file)r. '
                    'Supported version: %(supported_format_version)r') % locals()
        else:
            print('Missing layer VERSION for:', layer_dir)

        if not LAYER_JSON_FILE in files:
            print('Missing layer json for:', layer_dir)
            return Layer(layer_id=layer_id)

        # load data
        with open(join(layer_dir, LAYER_JSON_FILE)) as layer_json:
            layer_data = json.load(layer_json, object_pairs_hook=OrderedDict)

        # Note: it is possible to have an EMPTY layer.tar that is a link to another
        # non-empty layer.tar
        if LAYER_TAR_FILE in files:
            layer_tar = join(layer_dir, LAYER_TAR_FILE)
            layer_digest = sha256_digest(layer_tar)
            layer_size = filetype.get_size(layer_tar)
        else:
            layer_digest = None
            layer_size = 0

        # do not rely on this
        if 'Size' in layer_data:
            del layer_data['Size']

        # do not rely on this
        if 'id' in layer_data:
            lid = layer_data.pop('id')
            # make some basic checks
            assert layer_id == lid


        ccnf = layer_data.pop('container_config', {})
        cnf = layer_data.pop('config', {})
        config, warns = merge_configs(ccnf, cnf)
        if warns and verbose:
            print('Warning when loading: %(config_file)r' % locals())
            for w in warns:
                print(w)

        layer = Layer(layer_id=layer_id, layer_digest=layer_digest, layer_size=layer_size, 
                #config=config,
                **layer_data)
        layer.command = get_command(config.get('Cmd'))
        layer.labels = config.get('Labels')
        if not layer.author:
            layer.author = config.get('Author') or config.get('author')
        return layer

    @classmethod
    def merge(self, layers):
        """
        Return a new list of new Layer objects from a list of Layer objects and a
        list of warning message strings. The layers order is NOT preserved.

        Layer objects that are for the same layer (based on id, hash or path) are
        merged in a single updated object and attributes that are missing in one
        Layer are updated with the value from the other Layers. If two "same" Layer
        have conflicting (e.g different) values for the same attribute (excluding
        empty values), print and return warning messages too..
        """
        warnings = []
        merged = set()

        # remove trivial, exact duplicates
        layers = set(layers)

        # 1. build mapping for clustering
        by_digest = defaultdict(list)
        for layer in layers:
            by_digest[layer.layer_digest].append(layer)

        # layers with no digest or an empty digest are not merged (though
        # they could in the future using attribute similarities)
        merged.update(by_digest.pop(None, []))
        merged.update(by_digest.pop('', []))

        for similar_layers in by_digest.values():
            if len(similar_layers) == 1:
                merged.update(similar_layers)
            merged_layer = similar_layers.pop()
            for simi_layer in similar_layers:
                merged_layer, warns = merge_update_mappings(merged_layer, simi_layer)
                warnings.extend(warns)
            merged.append(merged_layer)

        return merged, warnings
