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

from collections import deque
from collections import OrderedDict
import json
import logging
from os.path import join
from os.path import isdir

import attr

from commoncode import filetype
from commoncode import fileutils
from commoncode.hash import sha256

from conan import NonSortableLayersError
from conan import DEFAULT_LAYER_ID_LEN
from conan import REPO_V11_MANIFEST_JSON_FILE
from conan import REPO_V10_REPOSITORIES_FILE
from conan import LAYER_VERSION_FILE
from conan import LAYER_JSON_FILE
from conan import LAYER_TAR_FILE

from conan.utils import listdir
from conan.utils import is_image_or_layer_id


logger = logging.getLogger(__name__)
# un-comment these lines to enable logging
# logging.basicConfig(level=logging.DEBUG, stream=sys.stdout)
# logger.setLevel(logging.DEBUG)


"""
Main objects to handle Docker repositories, images and layers data.
"""

class Images(object):
    """
    Represent a collection of images and their tags, and the FROM and shared
    layers relations that exists between these.
    """
    def __init__(self, images):
        """
        images is a list of ImageV10 objects.
        """
        self.images_by_id = self._build_images_by_id(images)
        self.graph = None

    def _build_images_by_id(self, images):
        """
        Given a list of Image objects, return a mapping of image id -> image.
        Each image object may appear multiple times.
        """
        image_by_id = {}
        for image in images:
            for iid in image.get_image_ids(image):
                assert iid not in image_by_id
                image_by_id[iid] = image
        return image_by_id


def get_image(location, echo=print, layerid_len=DEFAULT_LAYER_ID_LEN):
    """
    Return a dictionary location -> image object if the location is an ImageV10
    directory. Return an empty dictionary otherwise.
    """
    try:
        image = ImageV10(location, layerid_len=layerid_len)
        echo('Found Docker image at: %(location)r' % locals())
        return {location: image}
    except Exception, e:
        logger.debug('get_image: Not an image directory: %(location)r' % locals())
        # not an image
        return {}


class AttrODictMixin(object):

    def as_dict(self):
        return attr.asdict(self, dict_factory=OrderedDict)


@attr.attributes
class Registry(AttrODictMixin):
    """
    A collection of several Repositories that may not be related.
    """
    repositories = attr.attrib(
        default=attr.Factory(dict),
        metadata=dict(doc='a mapping of repo_dir->Repository object')
    )

    def unique_layers(self):
        """
        Return a list of unique layers in this registry.
        """
        raise NotImplementedError

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
        Return a mapping of layer_id-> [list of image ids where this layer is used]
        """
        raise NotImplementedError


@attr.attributes
class Repository(AttrODictMixin):
    """
    A collection of several related images stored in a common "repository" directory.
    """

    repo_dir = attr.attrib(
        metadata=dict(doc='the repository dir where the repo metadata exists (repositories, manifest.json)')
    )

    layers_by_id = attr.attrib(
        default=attr.Factory(dict),
        metadata=dict(doc='a mapping of (layer_id-> layer object) from bottom to top')
    )

    layers_by_hash = attr.attrib(
        default=attr.Factory(dict),
        metadata=dict(doc='a mapping of (sha256(layer.tar)-> layer object) from bottom to top')
    )

    layers_by_containerid = attr.attrib(
        default=attr.Factory(dict),
        metadata=dict(doc='a mapping of (container_id-> layer object) from bottom to top')
    )

    images = attr.attrib(
        default=attr.Factory(dict),
        metadata=dict(doc='a mapping of image_id-> image object')
    )

    repository_data = attr.attrib(
        default=attr.Factory(OrderedDict),
        metadata=dict(doc='Mapping of original repository data')
    )

    tags = attr.attrib(
        default=attr.Factory(OrderedDict),
        metadata=dict(doc='mapping of name:tag -> image id for images in this repository')
    )


def load_repositories(repositories):
    """
    Return "repositories" data.
    This is mapping with this shape:
    {
        "username/imagename": { "version1": "top layer id", "version2" : "top layer id", }
    }
    The layer id is the name of the layer.tar parent dir.
    """
    for image_name, versions in repositories.items():
        for version, top_layer_id in versions:
            pass
"""
 digestSHA256GzippedEmptyTar is the canonical sha256 digest of
// gzippedEmptyTar
const digestSHA256GzippedEmptyTar = digest.Digest("sha256:a3ed95caeb02ffe68cdd9fd84406680ae93d633cb16422d00e8a7c22955b46d4")
"""

def load_images_from_manifest(base_dir):
    """
    Yield images loaded from a "manifest.json".

    The 'manifest.json' data is in the form of:
    The `Config` field references another JSON file in the tar or repo which includes
    the image data for this image.

    The `RepoTags` field lists references pointing to this image.

    The `Layers` field points to the filesystem changeset tars, e.g. the path to
    the layer.tar files as a list ordered from bottom to top layer.

    An optional `Parent` field references the imageID (as a sha256) of the parent image. This
    parent must be part of the same `manifest.json` file.

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
    manifest_file = join(base_dir, REPO_V11_MANIFEST_JSON_FILE)
    manifest = load_json(manifest_file)

    for image_config in manifest:
        config_file = image_config.get('Config')
        image_id = fileutils.file_base_name(config_file)
        config_digest = sha256_digest(config_file)
        parent_digest = image_config.get('Parent')
        layer_paths = image_config.get('Layers', [])
        layers = OrderedDict()
        for lp in layer_paths:
            layer_id = fileutils.parent_directory(lp),
            layer_digest = sha256_digest(join(base_dir, lp)),
            layer = dict(
                layer_id=layer_id,
                layer_digest=layer_digest,
                layer_base_dir=join(base_dir, layer_id),
            )
            layers[layer_id] = layer
        top_layer_id = layer_id
        top_layer_digest = layer_digest

        tags = image_config.get('RepoTags', [])
        image = Image(
            image_dir=base_dir,
            image_id=image_id,
            tags=tags,
        )


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
        metadata=dict(doc='Mapping of original config data')
    )

    container_config = attr.attrib(
        default=attr.Factory(OrderedDict),
        metadata=dict(doc='Mapping of original container config data')
    )


@attr.attributes
class Image(AttrODictMixin, ConfigMixin):
    """
    A container image with pointers to its layers.
    """

    image_dir = attr.attrib(
        default=None,
        metadata=dict(doc='the base directory where the image is found, '
                          'typically the same as a repository dir')
    )

    image_id = attr.attrib(
        default=None,
        metadata=dict(doc='The id for this image. This is the base name of the config.json file.')
    )

    parent_digest = attr.attrib(
        default=None,
        metadata=dict(doc='The digest of the parent for this image.')
    )

    config_digest = attr.attrib(
        default=None,
        metadata=dict(doc='The digest of the config JSON file for this image.')
    )

    top_layer_id = attr.attrib(
        default=None,
        metadata=dict(doc='The top layer id for this image.')
    )

    top_layer_digest = attr.attrib(
        default=None,
        metadata=dict(doc='The top layer digest for this image.')
    )

    layers = attr.attrib(
        default=attr.Factory(OrderedDict),
        metadata=dict(doc='an Ordered mapping of (layer_id-> layer object) from bottom to top')
    )

    image_data = attr.attrib(
        default=attr.Factory(OrderedDict),
        metadata=dict(doc='Mapping of original image data')
    )

    tags = attr.attrib(
        default=attr.Factory(list),
        metadata=dict(doc='List of tags for this image as strings of user/name:version')
    )


@attr.attributes
class LayerConfigMixin(ConfigMixin):
    """
    Configuration data as found in a layer json file.
    """
    id = attr.attrib(
        default=None,
        metadata=dict(doc='layer id. LEGACY')
    )

    parent = attr.attrib(
        default=None,
        metadata=dict(doc='parent layer id. LEGACY.')
    )


@attr.attributes
class Layer(AttrODictMixin, LayerConfigMixin):
    """
    A layer object represents a slice of a root filesyetem.
    """
    format_version = '1.0'

#     layer_dir = attr.attrib(
#         default=None,
#         metadata=dict(doc='the base directory where the layer.tar is found. '
#                           'This should be a relative directory.')
#     )

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

    def is_noop(self):
        """
        Return True if this command was created by a "no op" command
        """
        cmd = self.command and self.command.strip() or ''
        return not cmd or '(nop)' in cmd

    def as_dict(self):
        ad = super(Layer, self).as_dict()
        ad['is_noop'] = self.is_noop()
        return ad

    @classmethod
    def load_layer(cls, layer_dir):
        """
        Return a Layer object built from layer metadata in the layer_dir.
        Raise an exception on errors.
        """
        if not layer_dir:
            return
        assert isdir(layer_dir)
        files = listdir(layer_dir)

        assert files
        logger.debug('load_layer: Layer files: ', files, 'layer_dir: ', layer_dir)

        # check that all the files we expect to be in the layer dir are present note:
        # we ignore any other files (such as extracted tars, etc)
        assert LAYER_VERSION_FILE in files
        assert LAYER_JSON_FILE in files

        # FIXME: it is possible to have an EMPTY layer.tar that is a link to another
        # empty layer.tar
        assert LAYER_TAR_FILE in files

        # infer from the directory
        layer_id = fileutils.file_name(layer_dir)

        # loda data
        with open(join(layer_dir, LAYER_JSON_FILE)) as layer_json:
            layer_data = json.load(layer_json, object_pairs_hook=OrderedDict)

        # make some basic checks
        assert layer_id == layer_data['id']

        layer_format_version_file = join(layer_dir, LAYER_VERSION_FILE)
        supported_format_version = cls.format_version
        with open(layer_format_version_file) as lv:
            layer_format_version = lv.read().strip()
            assert supported_format_version == layer_format_version, (
                'Unknown layer format version: %(layer_format_version)r '
                'in: %(layer_format_version_file)r. '
                'Supported version: %(supported_format_version)r') % locals()

        layer_tar = join(layer_dir, LAYER_TAR_FILE)
        layer_digest = sha256_digest(layer_tar)
        layer_size = filetype.get_size(layer_tar)
        if 'Size' in layer_data:
            del layer_data['Size']

        layer = Layer(layer_id=layer_id,
                      layer_digest=layer_digest, layer_size=layer_size,
                      **layer_data)
        cnf = layer.config
        ccnf = layer.container_config
        cmd = cnf.get('Cmd') or cnf.get('cmd') or ccnf.get('Cmd') or ccnf.get('cmd')
        layer.command = get_command(cmd)
        layer.labels = cnf.get('Labels') or cnf.get('labels') or ccnf.get('Labels') or ccnf.get('labels')
        if not layer.author:
            layer.author = cnf.get('Author') or cnf.get('author') or ccnf.get('Author') or ccnf.get('author')
        return layer


def get_command(cmd):
    """
    Clean the command for this layer.
    """
    # FIXME: this need to be cleaned further
    return cmd and ' '.join([c for c in cmd if not c.startswith(('/bin/sh', '-c',))]) or ''


def sha256_digest(location):
    return 'sha256:' + sha256(location)


class LayerOld(object):
    """
    A layer object represents a slice of a root filesyetem. It is created from its id
    and the location of the parent directory that contains this layer ID directory
    (with a layer.tar tarball payload, a json metadata file and VERSION file).
    """
    format_version = '1.0'

    def __init__(self, layer_id, layer_dir=None, **kwargs):
        """
        Create a layer based on a layer_id and a directory location or keyword
        arguments (using the same structure as the json layer file). Raise an
        exception if this is not a valid layer.
        Files existence checks are not performed if location is None.
        """
        logger.debug('Creating layer: fom %(layer_dir)r' % locals())

        self.layer_id = layer_id

        assert layer_dir or kwargs

        self.layer_dir = layer_dir

        # FIXME: For now, this can be truncated later, should be a property
        self.layer_id_short = layer_id

        self.layer_data = self.load_layer(layer_id, layer_dir)

        # kwargs are used for testing
        if kwargs:
            self.layer_data.update(kwargs)

        # set the parent (or None for the root/bottom layer).
        # Not used in v11 format
        self.parent_id = self.layer_data.get('parent')

        # use config and fallback to container_config (that could be empty)
        cnf = self.layer_data.get('config', {})
        ccnf = self.layer_data.get('container_config', {})
        cmd = cnf.get('Cmd') or cnf.get('cmd') or ccnf.get('Cmd') or ccnf.get('cmd')
        self.command = get_command(cmd)
        self.labels = (ccnf.get('Labels') or ccnf.get('labels') or cnf.get('Labels') or cnf.get('labels'))

        self.comment = self.layer_data.get('comment')
        self.author = self.layer_data.get('author')
        self.created = self.layer_data.get('created')
        self.docker_version = self.layer_data.get('docker_version', '')
        self.os = self.layer_data.get('os', '')
        self.architecture = self.layer_data.get('architecture')
        self.size = int(self.layer_data.get('size', 0) or self.layer_data.get('Size', 0))



    def load_layer(self, layer_id, layer_dir):
        """
        Load layer metadata from the layer_dir. Raise an exception on errors.
        """
        if not layer_dir:
            return {}
        assert isdir(layer_dir)
        files = listdir(layer_dir)

        assert files
        logger.debug('LayerOld files: ', files, 'layer_dir: ', layer_dir)

        # check that all the files we expect to be in the layer dir are present note:
        # we ignore any other files (such as extracted tars, etc)
        assert LAYER_VERSION_FILE in files
        assert LAYER_JSON_FILE in files

        # FIXME: it is possible to have an EMPTY layer.tar that is a link to another
        # empty layer.tar
        assert LAYER_TAR_FILE in files

        # loda data
        with open(join(self.layer_dir, LAYER_JSON_FILE)) as layer_json:
            layer_data = json.load(layer_json, object_pairs_hook=OrderedDict)

        # make some basic checks
        assert layer_id == layer_data['id']

        layer_format_version_file = join(layer_dir, LAYER_VERSION_FILE)
        supported_format_version = self.format_version
        with open(layer_format_version_file) as lv:
            layer_format_version = lv.read().strip()
            assert supported_format_version == layer_format_version, (
                'Unknown layer format version: %(layer_format_version)r '
                'in: %(layer_format_version_file)r. '
                'Supported version: %(supported_format_version)r') % locals()
        return layer_data

    def __repr__(self, *args, **kwargs):
        return 'LayerOld(layer_id=%(layer_id)r,  parent=%(parent_id)r)' % self.__dict__

    def as_dict(self):
        layer_data = OrderedDict()
        layer_data['layer_dir'] = self.layer_dir
        layer_data['layer_id'] = self.layer_id
        layer_data['parent_id'] = self.parent_id
        layer_data['command'] = self.command
        layer_data['layer_data'] = self.layer_data
        return layer_data

    @classmethod
    def sort(cls, layers):
        """
        Sort a list of layer objects based on their parent-child relationship. The first layer
        at index 0 is the bottom root layer, the latest layer is the "top" layer at index
        -1.

        NB: There are likely more efficient algorithms such as a topological sort.
        """
        if not layers:
            return layers

        assert all(isinstance(o, LayerOld) for o in layers)

        sortedl = deque()
        to_sort = deque(layers)

        # track the number of cycles to avoid infinite recursion if the layers are
        # not forming a linear ancestry
        max_cycles = len(layers) ** 2
        cycles = 0

        while to_sort:
            cycles += 1
            current = to_sort.popleft()
            # is this the first layer we process?
            if not sortedl:
                sortedl.append(current)
            # is the last layer our parent?
            elif current.parent_id == sortedl[-1].layer_id:
                sortedl.append(current)
            # is the first layer our child?
            elif current.layer_id == sortedl[0].parent_id:
                sortedl.appendleft(current)
            # we cannot decide yet, so add back current to the bottom our our stack
            else:
                to_sort.append(current)
                if cycles > max_cycles:
                    msg = ('Non-sortable layers list: breaking after %(max_cycles)r '
                           'cycles, with unsortable leftovers :%(to_sort)r' % locals())
                    raise NonSortableLayersError(msg)
        return list(sortedl)


class BaseImageRepo(object):
    """
    Represent a base Image repository in Docker containing layers and tags.
    These eventually points to several images.
    """
    version = None

    def __init__(self, location, layerid_len=DEFAULT_LAYER_ID_LEN):
        """
        Create an image repository based a directory location.
        Raise an exception if this is not a repository with valid layers.
        Subclass should override accordingly.
        """
        # the dir where the image is found
        self.repo_dir = location
        # images repo data if present
        self.repositories_data = OrderedDict()

        self.layerid_len = layerid_len

        # a mapping of layers
        self.layers = OrderedDict()
        # mapping of name:tag' -> layer id
        self.tags = OrderedDict()

    def get_image_ids(self):
        """
        Return a list of image IDs for an image. Images are identified by a
        name:tag and the corresponding layer ID as a string: owner/name:tag:lid
        """
        return ':'.join([name_tag, layer_id] for name_tag, layer_id in self.tags.items())

    def as_flat_dict(self):
        for i, l in enumerate(self.layers.values()):
            data = OrderedDict()
            data['repo_dir'] = self.repo_dir
            data['image_names'] = '\n'.join(self.tags)
            data['repo_tags'] = '\n'.join(tag for tag, lid in self.tags.items() if lid == l.layer_id)
            data['layer_order'] = str(i)
            data['layer_id_short'] = l.layer_id_short
            data['layer_command'] = l.command or ''
            data['layer_comment'] = l.command or ''
            data['layer_author'] = l.author or ''
            data['layer_size'] = l.size and str(l.size) or ''
            data['layer_created'] = l.created or ''
            data['layer_id'] = l.layer_id
            data['layer_parent_id'] = l.parent_id or ''
            yield data

    def as_dict(self):
        image_data = OrderedDict()
        image_data['repo_dir'] = self.repo_dir
        image_data['repo_tags'] = self.tags
        image_data['layers'] = [l.as_dict() for l in self.layers.values()]
        return image_data



class ImageV10(BaseImageRepo):
    """
    Represent a repository of Images in Docker format V1.0 organized in a repository
    of layers with tags, where each tag or layer is eventually usable as a base image
    in a FROM Dockerfile command for another image and therefore represents an image
    itself.
    """

    version = '1.0'

    def __init__(self, location, layerid_len=DEFAULT_LAYER_ID_LEN):
        """
        Create an image repository based a directory location.
        Raise an exception if this is not a repository with valid layers.
        """
        super(ImageV10, self).__init__(location, layerid_len)

        dir_contents = listdir(self.repo_dir)
        assert dir_contents

        # load the 'repositories' data if present
        self.repositories_data = OrderedDict()
        if REPO_V10_REPOSITORIES_FILE in dir_contents:
            with open(join(self.repo_dir, REPO_V10_REPOSITORIES_FILE)) as json_file:
                self.repositories_data = json.load(json_file, object_pairs_hook=OrderedDict)
            logger.debug('ImageV10: Location is a candidate image repository: '
                         '%(location)r with a "repositories" JSON file' % locals())
        else:
            logger.debug('ImageV10: Location: %(location)r has no "repositories" JSON file' % locals())

        # collect the layers if we have real layer ids as directories
        layer_ids = [layer_id for layer_id in dir_contents
                     if is_image_or_layer_id(layer_id, layerid_len)
                     and isdir(join(location, layer_id))]

        assert layer_ids

        logger.debug('ImageV10: Location is a candidate image repository: '
                     '%(location)r with valid layer dirs' % locals())

        # build layer objects proper
        layers = [LayerOld(layer_id, join(location, layer_id)) for layer_id in layer_ids]
        logger.debug('ImageV10: Created %d new layers' % len(layers))

        # sort layers, from bottom (root) [0] to top layer [-1]
        layers = LayerOld.sort(layers)

        # ... and keep a track of layers by id
        self.layers = OrderedDict((layer.layer_id, layer) for layer in layers)

        # collect image tags from the repositories.json
        self.tags = self.image_tags(self.repositories_data)

        # fix missing authors by reusing the previous layer author
        # TODO: is that really correct?
        last_author = None
        for l in self.layers.values():
            if not last_author:
                last_author = l.author and l.author.strip() or None
            if not l.author:
                l.author = last_author

    def image_tags(self, repositories_data, add_latest=False):
        """
        The 'repositories' data is in the form of:
        {
         'image_name1': {tag1: layer_id, tag2: layer_id, etc}
         'image_name2': {latest: layer_id, tag2: layer_id, etc}
        }

        We transform it in a simpler 'name:tag' -> layer id mapping and add the
        latest implicit tag if not present corresponding to the latest layer
        """
        layer_id_by_tag = OrderedDict()
        for image_name, tags in repositories_data.items():
            has_latest = False
            for tag, layer_id in tags.items():
                if tag == 'latest':
                    has_latest = True
                image_tag = ':'.join([image_name, tag])
                layer_id_by_tag[image_tag] = layer_id
            if not has_latest and add_latest:
                latest_layer_id = self.layers.keys()[-1]
                image_tag = ':'.join([image_name, 'latest'])
                layer_id_by_tag[image_tag] = latest_layer_id
        return layer_id_by_tag


class ImageV11(BaseImageRepo):
    """
    Represent an image repository in Docker format V1.1/1.2.
    """
    version = '1.1'

    def __init__(self, location, layerid_len=DEFAULT_LAYER_ID_LEN):
        """
        Create an image repository based on a directory location.
        Raise an exception if this is not a valid image repository.
        """
        super(ImageV11, self).__init__(location, layerid_len)

        dir_contents = listdir(self.repo_dir)
        assert dir_contents

        # load the 'manifest.json' data if present
        self.repositories = OrderedDict()
        if REPO_V11_MANIFEST_JSON_FILE in dir_contents:
            with open(join(self.repo_dir, REPO_V10_REPOSITORIES_FILE)) as json_file:
                self.repositories = json.load(json_file, object_pairs_hook=OrderedDict)
            logger.debug('ImageV11: Location is a candidate image repository: '
                         '%(location)r with a "manifest.json" JSON file' % locals())
        else:
            logger.debug('ImageV11: Location: %(location)r has no "manifest.json" JSON file' % locals())

        # collect the layers if we have real layer ids as directories
        layer_ids = [layer_id for layer_id in dir_contents
                     if is_image_or_layer_id(layer_id, layerid_len) and isdir(join(location, layer_id))]
        assert layer_ids
        logger.debug('ImageV10: Location is a candidate image repository: '
                     '%(location)r with valid layer dirs' % locals())
        # build layer objects proper and keep a track of layers by id
        layers = [LayerOld(layer_id, join(location, layer_id)) for layer_id in layer_ids]
        logger.debug('ImageV10: Created %d new layers' % len(layers))
        # sort layers, from bottom (root) [0] to top layer [-1]
        layers = LayerOld.sort(layers)
        self.layers = OrderedDict((layer.layer_id, layer) for layer in layers)

        self.tags = self.image_tags()

        # fix missing authors reusing the previous layer author
        last_author = None
        for l in self.layers.values():
            if not last_author:
                last_author = l.author and l.author.strip() or None
            if not l.author:
                l.author = last_author

    def image_tags(self, add_latest=False):
        layer_id_by_tag = OrderedDict()
        for image_name, tags in self.repositories.items():
            has_latest = False
            for tag, layer_id in tags.items():
                if tag == 'latest':
                    has_latest = True
                image_tag = ':'.join([image_name, tag])
                layer_id_by_tag[image_tag] = layer_id
            if not has_latest and add_latest:
                latest_layer_id = self.layers.keys()[-1]
                image_tag = ':'.join([image_name, 'latest'])
                layer_id_by_tag[image_tag] = latest_layer_id
        return layer_id_by_tag


    """
    Each Config JSON file for each image has this shape:
    {
        'architecture': 'amd64',
        'author': '<author name>',
        'config': { <some config k/v pairs> },
        'container': '1ee508bc7a35150c9e5924097a31dfb4b6b2ca1260deb6fd14cb03c53764e40b',
        'container_config': { <some config k/v pairs> },
        'created': '2016-09-30T10:16:27.109917034Z',
        'docker_version': '1.8.2',
        # array of objects describing the history of each layer.
        # The array is ordered from bottom-most layer to top-most layer.
        'history': [
            {'author': 'The CentOS Project <cloud-ops@centos.org> - ami_creator',
             'created': '2015-04-22T05:12:47.171582029Z',
             'created_by': '/bin/sh -c #(nop) MAINTAINER The CentOS Project <cloud-ops@centos.org> - ami_creator'
            },
            {'author': 'The CentOS Project <cloud-ops@centos.org> - ami_creator',
             'created': '2015-04-22T05:13:47.072498418Z',
             'created_by': '/bin/sh -c #(nop) ADD file:eab3c29917290b056db08167d3a9f769c4b4ce46403be2fad083bc2535fb4d03 in /'
            },
        ]
        'os': 'linux',
        # this is in order from bottom-most to top-most
        # each id is the sha256 of a layer.tar
        'rootfs': {
            'diff_ids': ['sha256:5f70bf18a086007016e948b04aed3b82103a36bea41755b6cddfaf10ace3c6ef',
                         'sha256:2436bc321ced91d2f3052a98ff886a2feed0788eb524b2afeb48099d084c33f5',
                         'sha256:cd141a5beb0ec83004893dfea6ea8508c6d09a0634593c3f35c0d433898c9322',]
            'type': u'layers'
        }
    }

    """


def load_json(location):
    """
    Load and return the data from a JSON file at `location`.
    Ensure that the mapping are ordered.
    """
    with open(location) as loc:
        data = json.loads(loc.read(), object_pairs_hook=OrderedDict)
    return data
