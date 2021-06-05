#
# Copyright (c) nexB Inc. and others. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
# See http://www.apache.org/licenses/LICENSE-2.0 for the license text.
# See https://github.com/nexB/container-inspector for support or download.
# See https://aboutcode.org for more information about nexB OSS projects.
#

import logging
import operator
import os
from os import path

import dockerfile_parse

TRACE = False
logger = logging.getLogger(__name__)
if TRACE:
    import sys
    logging.basicConfig(level=logging.DEBUG, stream=sys.stdout)
    logger.setLevel(logging.DEBUG)

"""
Analysis helper for Docker Dockerfiles.
"""


def get_dockerfile(location):
    """
    Return a Dockerfile data dictionary if the location is a Dockerfile,
    otherwise return None.
    """
    fn = path.basename(location)
    if not 'Dockerfile' in fn:
        return {}

    if TRACE: logger.debug('Found Dockerfile at: %(location)r' % locals())

    try:
        # TODO: keep comments instead of ignoring them:
        # assign the comments before an instruction line to a line "comment" attribute
        # assign end of line comment to the line
        # assign top of file and  end of file comments to file level comment attribute
        df = dockerfile_parse.DockerfileParser(location)

        df_data = dict()
        df_data['location'] = location
        df_data['base_image'] = df.baseimage
        df_data['instructions'] = []

        for entry in df.structure:
            entry = dict([(k, v) for k, v in sorted(entry.items())
                                 if k in ('instruction', 'startline', 'value',)])
            df_data['instructions'].append(entry)
        return {location: df_data}
    except:
        if TRACE: logger.debug('Error parsing Dockerfile at: %(location)r' % locals())
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


def collect_dockerfiles(location):
    """
    Collect all Dockerfiles in a directory tree. Return a map of location ->
    Dockerfile data
    """
    dfiles = {}
    for top, dirs, files in os.walk(location):
        for f in files:
            dfiles.update(get_dockerfile(path.join(top, f)))
    if TRACE: logger.debug('collect_dockerfiles: %(dfiles)r' % locals())
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
INSTRUCTION_MATCHERS = {
    # FROM is special because always empty in Layers
    'FROM': lambda d, l: True,
    # ADD is special because scratch layers can have a ADD file:xsdsd  or ADD
    # dir:xsdsd that cannot be matched to a Dockerfile
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

    if not cmd.startswith(tuple(INSTRUCTION_MATCHERS)):
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


def clean_created_by(created_by):
    """
    Return a clean and normalized layer "created_by" from a `created_by` command string.
    The `created_by` or "Cmd" or "Command" is found in either of these places:

    - as a Dockerfile instruction line

    - in images format V1.1 and up, in the <id>.json Config file of an image in the
      history.created_by attribute such as this plain string:
       'created_by': '/bin/sh -c #(nop) MAINTAINER The CentOS Project'

    - in the <layer id>/json JSON file of a layer (in 1.0 format) in the
      container_config.Cmd attribute or in the config.Cmd attribute . This attribute
      can be also lowercase "cmd" such as this list:

       "Cmd": ["/bin/sh", "-c", "#(nop) ", "LABEL Some other label=" ]
    """
    # True if the command is a no-op and has no effect on the layer root fs (e.g
    # label, comment, authior, etc)
    is_noop = False
    if isinstance(created_by, (list, tuple)):
        # this is a structure, pre-parsed command as found in a layer "json" file
        # we strip the prefix
        return ' '.join([c for c in created_by if not c.startswith(('/bin/sh', '-c',))])
    else:
        # a string as found in a Dockerfile or Config json
        pass


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
    commands. If aligned, the Dockerfile was used to create the corresponding
    Image layers.
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
    aligned_layers = dict()

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
            msg = ('Unable to align ImageV10 layers with Dockerfile instructions: '
                   'order=%(order)d, dckrfl_instruct=%(dckrfl_instruct)r, layer_instruct=%(layer_instruct)r' % locals())
            raise CannotAlignImageToDockerfileError(msg)

        has_same_command = INSTRUCTION_MATCHERS[dckrfl_instruct]
        if not has_same_command(dckrfl_cmd, layer_cmd):
            msg = ('Different commands for aligned layer and Dockerfile: '
                   'Dockerfile=%(dckrfl_cmd)r, layer=%(layer_cmd)r' % locals())
            raise AlignedInstructionWithDifferentCommandError(msg)


def match_images2dockerfiles(images, dockerfiles):
    """
    Given a list of ImageV10 objects and a list of Dockerfile dictionaries attempt
    to determine which Dockerfile was used for a given image, which ImageV10 Layers
    are for the base image.
    """

