#!/usr/bin/env python
import os, re, sys

from setuptools import setup

def get_version(package):
    init_py = open(os.path.join(package, '__init__.py')).read()
    return re.search("__version__ = ['\"]([^'\"]+)['\"]", init_py).group(1)

def get_description(package):
    init_py = open(os.path.join(package, '__init__.py')).read()
    return re.search("__description__ = ['\"]([^'\"]+)['\"]", init_py).group(1)

def get_packages(packages):
    return [
        dirpath
        for dirpath, _, _ in os.walk(packages)
        if os.path.exists(os.path.join(dirpath, '__init__.py'))
    ]

setup(
    name="yast",
    version=get_version('yast'),
    description=get_description('yast'),
    url='https://github.com/emryslou/yast',
    author='emrys.lou',
    author_email='1065873330@qq.com',
    packages=get_packages('yast'),
    package_dir={
        "yast": "yast",
    },
    extras_requires = {
        'full': [
            'requests',
            'aiofiles',
            'ujson',
            'python-multipart',
            'graphql-core < 3',
            'graphene',
            'isort',
            'itsdangerous',
        ],
        'test': [
            'pytest',
            'pytest-cov',
            'pytest-timeout',
            'black',
        ],
        'docs': [
            'mkdocs',
            'mkdocs-material',
        ]
    },
    classifiers=[
        'Programing Language Python :: 3.10.12',
    ],
)