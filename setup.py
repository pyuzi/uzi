#!/usr/bin/env python

from setuptools import setup, find_namespace_packages
from pathlib import Path

from Cython.Build import cythonize


setup(
    name="laza-di",
    version="0.0.3",
    author="David Kyalo",
    description="Dependency injection library",
    long_description=Path("README.md").read_text(),
    long_description_content_type="text/markdown",
    url="https://github.com/laza-toolkit/di",
    project_urls={
        "Bug Tracker": "https://github.com/laza-toolkit/di/issues",
    },
    classifiers=[
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
    ],
    packages=find_namespace_packages(include=['laza.di']),
    ext_modules=cythonize('laza/di/**/*.pyx'),
    include_package_data=True,
    python_requires="~=3.9",
    zip_safe=False,
    install_requires=[
        "blinker ~=1.4",
        "laza-common"
    ],
)
