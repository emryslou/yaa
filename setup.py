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
    name="yaa",
    version=get_version('yaa'),
    description=get_description('yaa'),
    url='https://github.com/emryslou/yaa',
    author='emrys.lou',
    author_email='1065873330@qq.com',
    packages=get_packages('yaa'),
    package_dir={
        "yaa": "yaa",
    },
    extras_requires = {
        'standard': [
            "anyio >= 4.0, < 5",
            "aiofiles",
            "databases[sqlite]",
            "httpx",
            "python-multipart",
            "types-ujson",
            "ujson",
            "trio==0.22.1",
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
            'cryptography',
        ],
        'itsdangerous': [
            'itsdangerous',
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
            "coverage >= 5.3",
            "mypy",
            "importlib-metadata",
            "pytest",
            "pytest-asyncio",
            "pytest-benchmark",
            "pytest-timeout",
            "types-contextvars==2.4.7",
            "types-dataclasses==0.6.6",
            "types-PyYAML==6.0.4",
            "types-requests==2.26.3",
            "typing_extensions==4.2.0",
        ],
        'dev': [
            "bandit",
            "black",
            "pylint",
            "ruff",
        ],
    },
    classifiers=[
        'Programing Language Python :: 3.10.12',
    ],
)