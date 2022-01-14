#!/usr/bin/env python

from setuptools import setup, find_namespace_packages
from pathlib import Path


setup(
    name="laza-di",
    version="0.0.1",
    author="David Kyalo",
    description="A python development toolkit",
    long_description=Path("README.md").read_text(),
    long_description_content_type="text/markdown",
    url="https://github.com/davidkyalo/laza-common",
    project_urls={
        "Bug Tracker": "https://github.com/davidkyalo/laza-common/issues",
    },
    classifiers=[
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
    ],
    packages=find_namespace_packages(include=['laza.di']),
    include_package_data=True,
    python_requires="~=3.9",
    zip_safe=True,
    install_requires=[
        "blinker ~=1.4",
        "laza-common"
    ],
)
