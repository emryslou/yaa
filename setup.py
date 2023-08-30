#!/usr/bin/env python
import os, re, sys

from setuptools import setup

def get_version(package):
    init_py = open(os.path.join(package, '__init__.py')).read()
    return re.search("__version__ = ['\"]([^'\"]+)['\"]", init_py).group(1)

setup(
    name="yast",
    version=get_version('yast'),
    url='https://github.com/emryslou/yast/',
    packages=['yast'],
    package_dir={
        "yast": "yast",
    }
)