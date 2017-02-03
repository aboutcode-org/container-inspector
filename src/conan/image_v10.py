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

from conan import DEFAULT_ID_LEN
from conan import REPOSITORIES_FILE
from conan import LAYER_VERSION_FILE
from conan import LAYER_JSON_FILE
from conan import LAYER_TAR_FILE
from conan import is_image_or_layer_id

from conan.utils import listdir
from conan.utils import get_command


logger = logging.getLogger(__name__)
# un-comment these lines to enable logging
# logging.basicConfig(level=logging.DEBUG, stream=sys.stdout)
# logger.setLevel(logging.DEBUG)


"""
Objects to handle Docker repositories, images and layers data in v1.0 format.
"""


class NonSortableLayersError(Exception):
    pass


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

    def __init__(self, location, layerid_len=DEFAULT_ID_LEN):
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

    def __init__(self, location, layerid_len=DEFAULT_ID_LEN):
        """
        Create an image repository based a directory location.
        Raise an exception if this is not a repository with valid layers.
        """
        super(ImageV10, self).__init__(location, layerid_len)

        dir_contents = listdir(self.repo_dir)
        assert dir_contents

        # load the 'repositories' data if present
        self.repositories_data = OrderedDict()
        if REPOSITORIES_FILE in dir_contents:
            with open(join(self.repo_dir, REPOSITORIES_FILE)) as json_file:
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

