#!/usr/bin/env python
# -*- encoding: utf-8 -*-

import io
import os
import re
from glob import glob
from os.path import basename
from os.path import dirname
from os.path import join
from os.path import relpath
from os.path import splitext

from setuptools import find_packages
from setuptools import setup


def read(*names, **kwargs):
    return io.open(
        join(dirname(__file__), *names),
        encoding=kwargs.get('encoding', 'utf8')
    ).read()


setup(
    name='conan',
    version='3.1.0',
    license='Apache-2.0',
    description='Docker-related utilities.',
    long_description='Docker-related utilities.',
    author='nexB Inc.',
    author_email='info@nexb.com',
    url='https://github.com/nexB/conan',
    packages=find_packages('src'),
    package_dir={'': 'src'},
    py_modules=[splitext(basename(path))[0] for path in glob('src/*.py')],
    include_package_data=True,
    zip_safe=False,
    classifiers=[
        # complete classifier list: http://pypi.python.org/pypi?%3Aaction=list_classifiers
        'Development Status :: 4 - Beta',
        'Intended Audience :: Developers',
        'Operating System :: POSIX :: Linux',
        'Operating System :: MacOS :: MacOS X',
        'Operating System :: Microsoft :: Windows',
        'Programming Language :: Python',
        'Programming Language :: Python :: 3',
        'Programming Language :: Python :: 3.6',
        'Topic :: Utilities',
    ],
    keywords=[],
    install_requires=[
        'click >= 6.0.0, < 7.0.0',
        'attrs',
        'dockerfile_parse',
        'unicodecsv',
    ],

    entry_points={
        'console_scripts': [
            'conan=conan.cli:conan',
            'conan_squash=conan.cli:conan_squash',
            'conan_rpms=conan.installed_rpms:conan_rpms',
            'conan_dockerfile=conan.cli:conan_dockerfile',
        ],
    },
)
