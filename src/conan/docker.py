# Copyright (c) 2016 nexB Inc. and others. All rights reserved.
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

from __future__ import print_function, absolute_import

from collections import deque
from collections import OrderedDict
import json
import logging
import operator
import os
from os.path import join
from os.path import exists
from os.path import isdir
import re
import sys

import click
import dockerfile_parse
import unicodecsv

from commoncode import fileutils
from commoncode import filetype
import extractcode
from extractcode import extract


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

See the specification saved at references/docker_image_spec_v1.md
and at https://github.com/docker/docker/blob/master/image/spec/v1.md

See also:
https://github.com/docker/docker/blob/eaa1fc41c6cbdf589831d607e86e0ee38c2d053f/docs/reference/api/docker_remote_api_v1.22.md#image-tarball-format

"""


REPOSITORIES_JSON_FILE = 'repositories'
LAYER_TAR_FILE = 'layer.tar'
LAYER_JSON_FILE = 'json'
LAYER_VERSION_FILE = 'VERSION'
LAYER_FILES = set([LAYER_TAR_FILE, LAYER_JSON_FILE, LAYER_VERSION_FILE])


docker_version = re.compile('docker/([^\s]+)')


DEFAULT_LAYER_ID_LEN = 64

def is_image_id(s, layerid_len=DEFAULT_LAYER_ID_LEN):
    """
    Return True if the string s looks like a layer ID.
    Checks at most layerid_len characters
    """
    return re.compile(r'^[a-f0-9]{%(layerid_len)d}$' % locals()).match


AUFS_SPECIAL_FILE_PREFIX = '.wh..wh.'
AUFS_WHITEOUT_PREFIX = '.wh.'

extracted = ('-extract', '-djcx',)


def listdir(location):
    """
    Return a list of files and directories in the location directory or an empty
    list. Ignore extracted directed directories..
    """
    if not isdir(location):
        return []
    return [f for f in os.listdir(location) if not f.endswith(extracted)]


class InconsistentLayersOderingError(Exception): pass


class NonSortableLayersError(Exception): pass


class Images(object):
    """
    Represent a collection of images and their tags, and the FROM and shared
    layers relations that exists between these.
    """
    def __init__(self, images):
        """
        images is a list of Image objects.
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

    def build_graph(self):
        """
        Build a graph from the images.
        """


class Image(object):
    """
    Represent a single stored Image organized in a repository of layers, where each tag
    or layer is eventually usable as a base image in a FROM Dockerfile command
    for another image.
    """

    def __init__(self, location, layerid_len=DEFAULT_LAYER_ID_LEN):
        """
        Create an image repository based a directory location.
        Raise an exception if this is not a repository with valid layers.
        """
        self.repo_dir = location

        dir_contents = listdir(self.repo_dir)
        assert dir_contents

        # load the 'repositories' data if present
        self.data = OrderedDict()
        if REPOSITORIES_JSON_FILE in dir_contents:
            with open(join(self.repo_dir, REPOSITORIES_JSON_FILE)) as json_file:
                self.data = json.load(json_file, object_pairs_hook=OrderedDict)
            logger.debug('Image: Location is a candidate repo: %(location)r with a "repositories" JSON file' % locals())
#         else:
#             logger.debug('Image: Location: %(location)r has no "repositories" JSON file' % locals())

        # collect the layers
        layer_ids = [n for n in dir_contents if n != REPOSITORIES_JSON_FILE]
        # check if we have real layer ids as directories
        has_possible_layers = all(isdir(join(location, n)) and is_image_id(n, layerid_len) for n in layer_ids)
        assert has_possible_layers
        logger.debug('Image: Location is a candidate repo: %(location)r with valid layer dirs' % locals())
        # build layer objects proper and keep a track of layers by id
        layers = [Layer(layer_id, join(location, layer_id)) for layer_id in layer_ids]
        logger.debug('Image: Created %d new layers' % len(layers))
        # sort layers, from bottom (root) [0] to top layer [-1]
        layers = sorted_layers(layers)
        self.layers = OrderedDict((layer.layer_id, layer) for layer in layers)

        self.tags = self._build_tags()

        # fix missing authors reusing the previous layer author
        last_author = None
        for l in self.layers.values():
            if not last_author:
                last_author = l.author and l.author.strip() or None
            if not l.author:
                l.author = last_author

    def _build_tags(self, add_latest=False):
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
        for image_name, tags in self.data.items():
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

    def get_image_ids(self):
        """
        Return a list of image IDs for an image. Images are identified by a
        name:tag and the corresponding layer ID as a string: owner/name:tag:lid
        """
        return ':'.join([name_tag, layer_id] for name_tag, layer_id in self.tags.items())

    def as_json(self):
        return json.dumps(self.as_dict(), indent=2,)

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
        data = OrderedDict()
        data['repo_location'] = self.repo_dir
        data['repo_tags'] = self.tags
        data['layers'] = [l.as_dict() for l in self.layers.values()]
        return data

    def extract_merge(self, target_dir, layerid_len=DEFAULT_LAYER_ID_LEN):
        """
        Extract and merge all layers to target_dir. Extraction is done in
        sequence from bottom (root) to top (latest layer).

        Return a mapping of errors and a list of whiteouts/deleted files.

        The extraction process consists of these steps:
         - extract the layer in a temp directory
         - move layer to the target directory, overwriting existing files
         - if any, remove AUFS special files/dirs in the target directory
         - if any, remove whiteouts file/directory pairs in the target directory
        """
        assert filetype.is_dir(target_dir)
        assert os.path.exists(target_dir)
        extract_errors = []
        # log whiteouts deletions
        whiteouts = []

        for layer_id, layer in self.layers.items():
            LAYER_TAR_FILE_file = join(self.repo_dir, layer_id[:layerid_len], LAYER_TAR_FILE)
            logger.debug('Extracting layer:' + LAYER_TAR_FILE_file)
            temp_target = fileutils.get_temp_dir('conan-docker')
            xevents = list(extract.extract_file(LAYER_TAR_FILE_file, temp_target))
            for x in xevents:
                if x.warnings or  x.errors:
                    extract_errors.extend(xevents)

            # move extracted layer to target_dir
            logger.debug('Moving layer from:' + temp_target + ' to:' + target_dir)
            fileutils.copytree(temp_target, target_dir)
            fileutils.delete(temp_target)

            logger.debug('Merging layers and applying AUFS whiteouts')
            for top, dirs, files in fileutils.walk(target_dir):
                # delete AUFS dirs and apply whiteout deletions
                for d in dirs[:]:
                    wd = join(top, d)
                    if d.startswith(AUFS_WHITEOUT_PREFIX):
                        # delete the .wh. dir...
                        dirs.remove(d)
                        logger.debug('Deleting wh dir:  %(wd)r' % locals())
                        fileutils.delete(wd)

                        # ... and delete the corresponding dir it does "whiteout"
                        base_dir = d[len(AUFS_WHITEOUT_PREFIX):]
                        try:
                            dirs.remove(base_dir)
                        except ValueError:
                            raise InconsistentLayersOderingError('Inconsistent layers ordering: missing directory to whiteout: %(base_dir)r' % locals())
                        wdo = join(top, base_dir)
                        logger.debug('Deleting real dir:  %(wdo)r' % locals())
                        fileutils.delete(wdo)
                        whiteouts.append(wdo)

                    # delete AUFS special dirs
                    elif d.startswith(AUFS_SPECIAL_FILE_PREFIX):
                        dirs.remove(d)
                        logger.debug('Deleting AUFS special dir:  %(wd)r' % locals())
                        fileutils.delete(wd)

                # delete AUFS files and apply whiteout deletions
                all_files = set(files)
                for f in all_files:
                    wf = join(top, f)
                    if f.startswith(AUFS_WHITEOUT_PREFIX):
                        # delete the .wh. marker file...
                        logger.debug('Deleting wh file:  %(wf)r' % locals())
                        fileutils.delete(wf)
                        # ... and delete the corresponding file it does "whiteout"
                        base_file = f[len(AUFS_WHITEOUT_PREFIX):]

                        wfo = join(top, base_file)
                        whiteouts.append(wfo)
                        if base_file in all_files:
                            logger.debug('Deleting real file:  %(wfo)r' % locals())
                            fileutils.delete(wfo)

                    # delete AUFS special files
                    elif f.startswith(AUFS_SPECIAL_FILE_PREFIX):
                        logger.debug('Deleting AUFS special file:  %(wf)r' % locals())
                        fileutils.delete(wf)
                        whiteouts.append(wf)

        return extract_errors, whiteouts


class Layer(object):
    """
    A Docker layer object created from its id and the location of the parent
    directory that contains this layer ID directory and tarball payload.
    """

    def __init__(self, layer_id, location=None, **kwargs):
        """
        Create a layer based on a layer_id and a directory location or keyword
        arguments (using the same structure as the json layer file). Raise an
        exception if this is not a valid layer.
        Files existence checks are not performed if location is None.
        """
        logger.debug('Layer: Creating at %(location)r' % locals())
        assert location or kwargs
        self.base_dir = None
        self.layer_dir = None

        self.data = OrderedDict()

        self.layer_id = layer_id
        self.layer_id_short = layer_id
        if not location and len(layer_id) != DEFAULT_LAYER_ID_LEN:
            self.layer_id = self.data['id']

        if location:
            self.base_dir = location
            self.layer_dir = location
            assert isdir(self.layer_dir)

            files = listdir(self.layer_dir)
            assert files
            # check that all the files we expect to be in the layer dir are
            # present note: we ignore any other files (such as extracted tars,
            # etc)
            assert all(lf in set(files) for lf in LAYER_FILES)
            with open(join(self.layer_dir, LAYER_JSON_FILE)) as layer_json:
                self.data = json.load(layer_json, object_pairs_hook=OrderedDict)

            if len(layer_id) != DEFAULT_LAYER_ID_LEN:
                assert layer_id in self.data['id']
                self.layer_id = self.data['id']
            else:
                assert layer_id == self.data['id']

            assert exists(join(self.layer_dir, LAYER_VERSION_FILE))
            with open(join(self.layer_dir, LAYER_VERSION_FILE)) as lv:
                assert '1.0' == lv.read().strip()

        else:
            self.data.update(kwargs)

        # set the parent (or None for the root layer)
        self.parent_id = self.data.get('parent')

        # find the command for this layer
        conf = self.data.get('config', {})
        cont_conf = self.data.get('container_config', {})
        cmd = (cont_conf.get('Cmd', [])
               or cont_conf.get('cmd', [])
               # fallback to plain conf
               or conf.get('Cmd', [])
               or conf.get('cmd', [])
               )
        self.command = ' '.join([c for c in cmd if not c.startswith(('/bin/sh', '-c',))])

        self.comment = self.data.get('comment')

        # labels
        self.labels = (cont_conf.get('Labels', OrderedDict())
               or cont_conf.get('labels', OrderedDict())
               # fallback to plain conf
               or conf.get('Labels', OrderedDict())
               or conf.get('labels', OrderedDict())
               )


        # find other attributes for this layer
        self.author = self.data.get('author')
        self.created = self.data.get('created')
        self.docker_version = self.data.get('docker_version', '')
        self.os = self.data.get('os', '')
        self.architecture = self.data.get('architecture')
        self.size = int(self.data.get('size', 0) or self.data.get('Size', 0))

    def __repr__(self, *args, **kwargs):
        return 'Layer(layer_id=%(layer_id)r,  parent=%(parent_id)r)' % self.__dict__

    def as_dict(self):
        data = OrderedDict()
        data['base_dir'] = self.base_dir
        data['layer_dir'] = self.layer_dir
        data['layer_id'] = self.layer_id
        data['parent_id'] = self.parent_id
        data['command'] = self.command
        data['data'] = self.data
        return data


def sorted_layers(layers):
    """
    Sort a list of layers based on their parent-child relationship. The first
    layer at index 0 is the root layer, the latest layer is the "top" layer at
    index -1

    NB: There are likely more efficient or general algorithms such as a
    topological sort.
    """
    if not layers:
        return layers

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
                raise NonSortableLayersError('Non-sortable layers list: breaking after %(max_cycles)r cycles, with unsortable leftovers :%(to_sort)r' % locals())
    return list(sortedl)


def get_image(location, echo=print, layerid_len=DEFAULT_LAYER_ID_LEN):
    """
    Return a dictionary location -> image object if the location is an Image
    directory. Return an empty dictionary otherwise.
    """
    try:
        image = Image(location, layerid_len=layerid_len)
        echo('Found Docker image at: %(location)r' % locals())
        return {location: image}
    except:
        logger.debug('get_image: Not an image directory: %(location)r' % locals())
        # not an image
        return {}


def collect_images(location, echo=print, layerid_len=DEFAULT_LAYER_ID_LEN):
    """
    Collect all images in a directory tree. Return a map of location ->
    Image
    """
    images = {}
    for top, dirs, files in fileutils.walk(location):
        images.update(get_image(top, echo, layerid_len=layerid_len))
        for d in dirs:
            images.update(get_image(join(top, d), echo, layerid_len=layerid_len))
    logger.debug('images: %(images)r' % locals())
    return images


def collect_and_extract_merge(location, echo=print, layerid_len=DEFAULT_LAYER_ID_LEN):
    """
    Collect all images in a directory tree. Extract/merges the layers side-by-
    side with the image directory with an extract suffix.
    """
    all_wh = {}
    for loc, image in collect_images(location, echo, layerid_len=layerid_len).items():
        extract_target = loc.rstrip('\\/') + extractcode.EXTRACT_SUFFIX
        fileutils.create_dir(extract_target)
        echo('Extracting/merging layers for Docker image %(loc)r \n  to: %(extract_target)r' % locals())
        errors, whiteouts = image.extract_merge(extract_target, layerid_len=layerid_len)
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


def get_dockerfile(location, echo=print):
    """
    Return a Dockerfile data dictionary if the location is a Dockerfile,
    otherwise return None.
    """
    if not location.endswith('Dockerfile'):
        return {}
    echo('Found Dockerfile at: %(location)r' % locals())
    try:
        # TODO: keep comments:
        # assign all comments before an instruction line to the line
        # assign end of line comment to the line
        df = dockerfile_parse.DockerfileParser(location)

        df_data = OrderedDict()
        df_data['location'] = location
        df_data['base_image'] = df.baseimage
        df_data['instructions'] = []

        for entry in df.structure:
            entry = OrderedDict([(k, v) for k, v in sorted(entry.items()) if k in ('instruction', 'startline', 'value',)])
            df_data['instructions'].append(entry)
        return {location: df_data}
    except:
        echo('Error parsing Dockerfile at: %(location)r' % locals())
        return {}


def flatten_dockerfiles(dockerfiles):
    """
    Given a dict of (loc, Dockerfile), flatten as a list of dictionaries of:
    'location', 'base_image', 'order', 'instruction', 'value'
    """
    for loc, df in dockerfiles.items():
        for order, instruction in enumerate(df['instructions']):
            ndf = dict(order=order)
            ndf.update(instruction)
            del ndf['startline']
            ndf['location'] = loc
            ndf['base_image'] = df['base_image']
            yield ndf


def collect_dockerfiles(location, echo=print):
    """
    Collect all Dockerfiles in a directory tree. Return a map of location ->
    Dockerfile data
    """
    dfiles = {}
    for top, dirs, files in fileutils.walk(location):
        for f in files:
            dfiles.update(get_dockerfile(join(top, f), echo))
    logger.debug('collect_dockerfiles: %(dfiles)r' % locals())
    return dfiles


def all_strings_in(d, l):
    return all(x.strip('\'"') in l for x in d.split())


def add_equals_or_unknown(d, l):
    if 'file:' in l or 'dir:' in l:
        return True
    else:
        return d == l

# map of a Docker instruction to the comparison callable used when matching a
# Layer command to a Docker file command
# the callable args are: dockerfile_cmd, layer_cmd
INSTRUCTIONS = {
    # FROM is special because always empty in Layers
    'FROM': lambda d, l: True,
    # ADD is special because scratch layers can have a ADD file:xsdsd  or ADD dir:xsdsd that cannot be matched to a Dockerfile
    'ADD': add_equals_or_unknown,
    'WORKDIR': operator.eq,
    'CMD': all_strings_in,
    'ENV': operator.eq,
    'EXPOSE': all_strings_in,
    'MAINTAINER': operator.eq,
    'VOLUME': operator.contains,
    'RUN': operator.eq,
    # these are less common instructionds
    'COPY': operator.eq,
    'LABEL': operator.eq,
    'ENTRYPOINT': operator.eq,
    'USER': operator.eq,
    # this further executes commands from the base on build!
    'ONBUILD': operator.eq,
}


def normalized_layer_command(layer_command):
    """
    Given a layer_command string, return the instruction and normalized command
    for this layer extracted from the layer command and normalized to look like
    they were in the original Dockerfile.
    """
    cmd = layer_command and layer_command.strip() or ''
    cmd = cmd.replace('#(nop) ', '', 1)
    cmd = cmd.strip()

    if not cmd:
        instruct = 'FROM'
        cmd = ''
        return instruct, cmd

    if not cmd.startswith(tuple(INSTRUCTIONS)):
        # RUN instructions are not kept
        instruct = 'RUN'
    else:
        instruct, _, cmd = cmd.partition(' ')
        instruct = instruct.strip()
        cmd = cmd.strip()

    if instruct in ('ADD', 'COPY',):
        # normalize ADD and COPY commands
        # #(nop) ADD src/docker/fs/ in /
        cmd = cmd.replace(' in ', ' ', 1)

    shell = '[/bin/sh -c '
    if instruct == 'CMD' and cmd.startswith(shell):
        # normalize CMD
        # #(nop) CMD [/bin/sh -c ./opt/bin/startup.sh && supervisord -c /etc/supervisord.conf]
        cmd = cmd.replace(shell, '', 1)
        cmd = cmd.strip('[]')

    return instruct, cmd


class ImageToDockerfileAlignmentError(Exception):
    """Base alignment error"""


class CannotAlignImageToDockerfileError(ImageToDockerfileAlignmentError):
    pass


class AlignedInstructionWithDifferentCommandError(ImageToDockerfileAlignmentError):
    pass


def map_image_to_dockerfile(image, dockerfile):
    """
    Given an Image object and Dockerfile dictionary attempt to align the
    Dockerfile instructions and commands to the Image layers instructions and
    commands. If aligned, the Dockerfile was used to create the
    corresponding Image layers.
    """
    # collect and remove the FROM image instruction of the dockerfile
    # because it never exists in the layers
    from_base = dockerfile['instructions'].pop(0)
    from_image_instruction = from_base['instruction']
    assert from_image_instruction == 'FROM'
    from_image_startline = from_base['startline']
    from_image_name_tag = from_base['value'].strip()
    from_image_name, _, from_image_tag = from_image_name_tag.partition(':')


    # align layers and dockerfile lines, from top to bottom
    aligned = map(None, reversed(image.layers), reversed(dockerfile['instructions']))

    # TODO: keep track of original image for these layers
    base_image_layers = []
    aligned_layers = OrderedDict()

    for order, aln in enumerate(aligned):
        layer, dockerfile_instruct = aln
        if not dockerfile_instruct:
            # an unaligned layer comes from the base image
            base_image_layers.append(layer)
            continue

        layer_instruct, layer_cmd = normalized_layer_command(layer.command)
        dckrfl_instruct, dckrfl_startline, dckrfl_cmd = dockerfile_instruct.values()

        # verify command and instruction
        if not dckrfl_instruct == layer_instruct:
            raise CannotAlignImageToDockerfileError('Unable to align Image layers with Dockerfile instructions: order=%(order)d, dckrfl_instruct=%(dckrfl_instruct)r, layer_instruct=%(layer_instruct)r' % locals())

        has_same_command = INSTRUCTIONS[dckrfl_instruct]
        if not has_same_command(dckrfl_cmd, layer_cmd):
            raise AlignedInstructionWithDifferentCommandError('Different commands for aligned layer and Dockerfile: Dockerfile=%(dckrfl_cmd)r, layer=%(layer_cmd)r' % locals())


def find_shortest_prefix_length(strings):
    """
    Given a list of strings, return the smallest length that could be used to
    truncate these strings such that they still would be uniquely identified by this
    truncated prefix. Used to shorten long hash-like Layer Ids in the context of a
    bunch of Image layers analyzed together.
    """
    uniques = set(strings)
    shortest_len = max(len(s) for s in uniques)
    unique_count = len(uniques)
    # iterate the range of possible length backwards
    # start=shortest_len - 1, stop=0, step=-1
    for length in range(shortest_len - 1, 0, -1):
        truncated = set(s[:length] for s in uniques)
        if len(truncated) == unique_count:
            shortest_len = length
            continue
        else:
            break
    return shortest_len


def match_images2dockerfiles(images, dockerfiles):
    """
    Given a list of Image objects and a list of Dockerfile dictionaries attempt
    to determine which Dockerfile was used for a given image, which Image Layers
    are for the base image.
    """


@click.command()
@click.argument('directory', type=click.Path(exists=True, readable=True))
@click.option('-e', '--extract', is_flag=True, is_eager=True, help='Find built Docker images and their layers. For each image found, extract and merge all layers in a single rootfs-like structure.')
@click.option('--image_json', is_flag=True, is_eager=True, help='Find built Docker images and their layers. Print information as JSON.')
@click.option('-c', '--image_csv', is_flag=True, is_eager=True, help='Find built Docker images and their layers. Print information as CSV.')
@click.option('--dockerfile_json', is_flag=True, is_eager=True, help='Find source Dockerfile files. Print information as JSON.')
@click.option('-d', '--dockerfile_csv', is_flag=True, is_eager=True, help='Find source Dockerfile files. Print information  as CSV.')
@click.option('--layerid_len', default=DEFAULT_LAYER_ID_LEN, help='Use an different layer ID length than the default 64 characters.')
@click.help_option('-h', '--help')
def docker(directory, extract=False, image_json=False, image_csv=False, dockerfile_json=False, dockerfile_csv=False, layerid_len=DEFAULT_LAYER_ID_LEN):
    """
    Search input for Docker images in DIRECTORY.
    Either extract and merge found Docker images in an "-extract" directory and print results.
    Or print information about the Docker images and their layers (printed in sequence) as json.
    Use --help for help
    The CSV or JSON output are printed to screen. Use a > redirect to save in a file.
    """
    loc = os.path.abspath(os.path.expanduser(directory))
    if extract:
        collect_and_extract_merge(loc, echo=click.echo)
        return

    if image_json:
        click.echo(json.dumps([image.as_dict() for _loc, image in collect_images(loc, echo=no_print, layerid_len=layerid_len).items()], indent=2))
        return

    if image_csv:
        data = [list(image.as_flat_dict()) for _, image in collect_images(loc, echo=no_print, layerid_len=layerid_len).items()]
        if not data:
            return
        keys = data[0][0].keys()
        w = unicodecsv.DictWriter(sys.stdout, keys, encoding='utf-8')
        w.writeheader()
        for d in data:
            for i in d:
                w.writerow(i)
        return

    if dockerfile_json:
        click.echo(json.dumps([df for _loc, df in collect_dockerfiles(loc, echo=no_print).items()], indent=2))
        return

    if dockerfile_csv:
        data = collect_dockerfiles(loc, echo=no_print)
        if not data:
            return
        data = list(flatten_dockerfiles(data))
        keys = data[0].keys()
        w = unicodecsv.DictWriter(sys.stdout, keys, encoding='utf-8')
        w.writeheader()
        for d in data:
            w.writerow(d)
        return
