#!/usr/bin/env python

from setuptools import setup, find_packages
from pathlib import Path


setup(
    name="xdi",
    version="0.1.0",
    author="David Kyalo",
    description="Dependency injection library",
    long_description=Path("README.md").read_text(),
    long_description_content_type="text/markdown",
    url="https://github.com/davidkyalo/xdi",
    project_urls={
        "Bug Tracker": "https://github.com/davidkyalo/xdi/issues",
    },
    classifiers=[
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
    ],
    # packages=find_namespace_packages(include=['laza.di']),
    packages=find_packages(include=['xdi']),
    include_package_data=True,
    python_requires="~=3.9",
    zip_safe=False,
    install_requires=[
        "typing-extensions",

    ],
)
