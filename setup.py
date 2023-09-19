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
        'standard': [
            'requests',
            'aiofiles',
            'ujson',
            'python-multipart',
            'itsdangerous',
        ],
        'db': [
            'sqlalchemy >= 1.0, < 2.0.0',
        ],
        'postgresql': [
            'asyncpg',
            'psycopg2-binary',
        ],
        'mysql': [
            'aiomysql',
            'pymysql',
        ],
        'template': [
            'jinja2',
        ],
        'graphql': [
            'graphql-core < 3',
            'graphene',
        ],
        'schema': [
            'pyyaml',
        ],
        'test': [
            'pytest',
            'pytest-cov',
            'pytest-timeout',
        ],
        'dev': [
            'black',
            'isort',
            'mkdocs',
            'mkdocs-material',
            'flake8',
        ],
    },
    classifiers=[
        'Programing Language Python :: 3.10.12',
    ],
)