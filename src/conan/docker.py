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
from os.path import exists
from os.path import isdir

import attr

from conan import NonSortableLayersError
from conan import DEFAULT_LAYER_ID_LEN
from conan import LAYER_FILES
from conan import LAYER_JSON_FILE
from conan import LAYER_VERSION_FILE
from conan import REPOSITORIES_JSON_FILE_V11
from conan import MANIFEST_JSON_FILE_V10

from conan.utils import listdir
from conan.utils import is_image_or_layer_id


logger = logging.getLogger(__name__)
# un-comment these lines to enable logging
# logging.basicConfig(level=logging.DEBUG, stream=sys.stdout)
# logger.setLevel(logging.DEBUG)


"""
Analysis helper for Docker Dockerfiles, images, their layers and how these
relate to each other.

This modules provides utilities to:
 - identify Docker images in a file system and its layers and layer archives and
   JSON files.

 - given a Docker image, collect and report its metadata.

 - given Docker image layers, extract the layers using the docker image spec

Procedure to reconstruct the would-be image root-fs.
  - find and parse Dockerfiles
  - future: find how Dockerfiles relate to actual images.

 - future: given collected Dockerfiles, Images and their layers, build a graphviz
  graphic of the relationships between all these elements.

When stored in an image format or in a "V1 registry format", a docker image is a
directory that contains an optional "repositories" JSON file, and sub-
directories named after the IDs of each "layer". Each of this directories
contains a "layer.tar" tarball with the layer payload, a "json" JSON metadata
file describing the layer and a "VERSION" file describing the Docker version..
Each tarball represents a slice or diff of the image root file system using the
AUFS conventions.

In a sequence of layers each is "layered" on top of each other from the root
layer to the latest (or selected tagged layer) at runtime using the AUFS union
file system. In AUFS, any files prefixed with .wh. are "white outs" files
deleting files in the underlying layers.

See the specifications saved in docs/references/
This script implements V1.0

Additional specs for v1.1 and v1.2 are not yet supported though they offer some
backward compatibility with v1.0

See also:
https://github.com/docker/docker/blob/eaa1fc41c6cbdf589831d607e86e0ee38c2d053f/docs/reference/api/docker_remote_api_v1.22.md#image-tarball-format

"""


"""
Model:
And we can have multiple repositories in a DB.

[Registry]
  [Repository]
    [Layer]
    [Image]
      [Layer pointers]
        installed packages
        inventory
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



@attr.attributes
class Registry(object):
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
class Repository(object):
    """
    A collection of several related images stored in a common "repository" directory.
    """

    repo_dir = attr.attrib(
        metadata=dict(doc='the repository dir where the repo metadata exists (repositories, manifest.json)')
    )

    layers = attr.attrib(
        default=attr.Factory(dict),
        metadata=dict(doc='a mapping of (layer_id-> layer object) from bottom to top')
    )

    images = attr.attrib(
        default=attr.Factory(dict),
        metadata=dict(doc='a mapping of image_id-> image object')
    )


    repository_data =  attr.attrib(
        default=attr.Factory(OrderedDict),
        metadata=dict(doc='Mapping of original repository data')
    )

    tags =  attr.attrib(
        default=attr.Factory(OrderedDict),
        metadata=dict(doc='mapping of name:tag -> image id for images in this repository')
    )


@attr.attributes
class Image(object):
    """
    A container image with pointers to its layers.
    """

    base_dir = attr.attrib(
        metadata=dict(doc='the base directory where the image is found, typically the repository dir')
    )

    layers = attr.attrib(
        default=attr.Factory(OrderedDict),
        metadata=dict(doc='an Ordered mapping of (layer_id-> layer object) from bottom to top')
    )

    image_data =  attr.attrib(
        default=attr.Factory(OrderedDict),
        metadata=dict(doc='Mapping of original image data')
    )
    tags =  attr.attrib(
        default=attr.Factory(OrderedDict),
        metadata=dict(doc='mapping of name:tag -> id for this image')
    )


class Layer(object):
    """
    A layer object represents a slice of a root filesyetem. It is created from its id
    and the location of the parent directory that contains this layer ID directory
    (with a layer.tar tarball payload, a json metadata file and VERSION file).
    """
    format_version = '1.0'

    def __init__(self, layer_id, location=None, **kwargs):
        """
        Create a layer based on a layer_id and a directory location or keyword
        arguments (using the same structure as the json layer file). Raise an
        exception if this is not a valid layer.
        Files existence checks are not performed if location is None.
        """
        logger.debug('Creating layer: fom %(location)r' % locals())
        assert location or kwargs
        self.base_dir = None
        self.layer_dir = None

        self.layer_data = OrderedDict()

        self.layer_id = layer_id
        self.layer_id_short = layer_id
        if not location and len(layer_id) != DEFAULT_LAYER_ID_LEN:
            self.layer_id = self.layer_data['id']

        if location:
            self.base_dir = base_dir = location
            self.layer_dir = layer_dir = location
            assert isdir(layer_dir)

            files = listdir(layer_dir)
            assert files
            # check that all the files we expect to be in the layer dir are
            # present note: we ignore any other files (such as extracted tars,
            # etc)
            logger.debug('')
            logger.debug('Files: ', files, 'layer_dir: ', layer_dir)
            # FIXME: it is possible to have an EMPTY layer.tar that is a link to
            # another empty layer.tar
            assert all(lf in set(files) for lf in LAYER_FILES)
            with open(join(self.layer_dir, LAYER_JSON_FILE)) as layer_json:
                self.layer_data = json.load(layer_json, object_pairs_hook=OrderedDict)

            if len(layer_id) != DEFAULT_LAYER_ID_LEN:
                assert layer_id in self.layer_data['id']
                self.layer_id = self.layer_data['id']
            else:
                assert layer_id == self.layer_data['id']

            layer_format_version_file = join(layer_dir, LAYER_VERSION_FILE)
            assert exists(layer_format_version_file)
            supported_format_version = self.format_version
            with open(layer_format_version_file) as lv:
                layer_format_version = lv.read().strip()
                assert supported_format_version == layer_format_version, (
                    'Unknown layer format version: %(layer_format_version)r '
                    'in: %(layer_format_version_file)r. '
                    'Supported version: %(supported_format_version)r') % locals()

        else:
            self.layer_data.update(kwargs)

        # set the parent (or None for the root layer)
        self.parent_id = self.layer_data.get('parent')

        # find the command for this layer
        conf = self.layer_data.get('config', {})
        cont_conf = self.layer_data.get('container_config', {})
        cmd = (cont_conf.get('Cmd', [])
               or cont_conf.get('cmd', [])
               # fallback to plain conf
               or conf.get('Cmd', [])
               or conf.get('cmd', [])
               )
        self.command = ' '.join([c for c in cmd if not c.startswith(('/bin/sh', '-c',))])

        self.comment = self.layer_data.get('comment')

        # labels
        self.labels = (cont_conf.get('Labels', OrderedDict())
               or cont_conf.get('labels', OrderedDict())
               # fallback to plain conf
               or conf.get('Labels', OrderedDict())
               or conf.get('labels', OrderedDict())
               )


        # find other attributes for this layer
        self.author = self.layer_data.get('author')
        self.created = self.layer_data.get('created')
        self.docker_version = self.layer_data.get('docker_version', '')
        self.os = self.layer_data.get('os', '')
        self.architecture = self.layer_data.get('architecture')
        self.size = int(self.layer_data.get('size', 0) or self.layer_data.get('Size', 0))

    def __repr__(self, *args, **kwargs):
        return 'Layer(layer_id=%(layer_id)r,  parent=%(parent_id)r)' % self.__dict__

    def as_dict(self):
        layer_data = OrderedDict()
        layer_data['base_dir'] = self.base_dir
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
    
        assert all(isinstance(o, Layer) for o in layers)
    
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
            data['repo_location'] = self.repo_dir
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
        image_data['repo_location'] = self.repo_dir
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
        if REPOSITORIES_JSON_FILE_V11 in dir_contents:
            with open(join(self.repo_dir, REPOSITORIES_JSON_FILE_V11)) as json_file:
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
        layers = [Layer(layer_id, join(location, layer_id)) for layer_id in layer_ids]
        logger.debug('ImageV10: Created %d new layers' % len(layers))

        # sort layers, from bottom (root) [0] to top layer [-1]
        layers = Layer.sort(layers)

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
        if MANIFEST_JSON_FILE_V10 in dir_contents:
            with open(join(self.repo_dir, REPOSITORIES_JSON_FILE_V11)) as json_file:
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
        layers = [Layer(layer_id, join(location, layer_id)) for layer_id in layer_ids]
        logger.debug('ImageV10: Created %d new layers' % len(layers))
        # sort layers, from bottom (root) [0] to top layer [-1]
        layers = Layer.sort(layers)
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
    The 'manifest.json' data is in the form of:
        The `Config` field references another file in the tar which includes the image
        JSON for this image.

        The `RepoTags` field lists references pointing to this image.

        The `Layers` field points to the filesystem changeset tars.

        An optional `Parent` field references the imageID of the parent image. This
        parent must be part of the same `manifest.json` file.

    [
        {'Config': '7043867122e704683c9eaccd7e26abcd5bc9fea413ddfeae66166697bdcbde1f.json',
         'Layers': [
             '768d4f50f65f00831244703e57f64134771289e3de919a576441c9140e037ea2/layer.tar',
             '6a630e46a580e8b2327fc45d9d1f4734ccaeb0afaa094e0f45722a5f1c91e009/layer.tar',
             ]
         'RepoTags': ['user/image:version']
         },

        {'Config': '7043867122e704683c9eaccd7e26abcd5bc9fea413ddfeae66166697bdcbde1f.json',
         'Layers': [
             '768d4f50f65f00831244703e57f64134771289e3de919a576441c9140e037ea2/layer.tar',
             '6a630e46a580e8b2327fc45d9d1f4734ccaeb0afaa094e0f45722a5f1c91e009/layer.tar',
             ]
         'RepoTags': ['user/image:version']
         },
    ]

    and then each Config JSON file for each image has this shape:
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

