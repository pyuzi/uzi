#!/usr/bin/env python

from setuptools import setup, find_namespace_packages
from pathlib import Path



setup(
    name="Jani-DI",
    version="0.0.1",
    author="David Kyalo",
    description="A python development toolkit",
    long_description=Path("README.md").read_text(),
    long_description_content_type="text/markdown",
    url="https://github.com/davidkyalo/jani-common",
    project_urls={
        "Bug Tracker": "https://github.com/davidkyalo/jani-common/issues",
    },
    classifiers=[
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
    ],
    packages=find_namespace_packages(include=["jani.di"]),
    include_package_data=True,
    python_requires="~=3.9",
    # install_requires=["typing-extensions >=4.0.1"],
    # extras_require={
    #     "json": ["orjson>=3.6.5"],
    #     "locale": ["Babel >=2.9.1"],
    #     "moment": ["arrow >=1.2.1"],
    #     "money": ["Jani-Common[locale]", "py-moneyed >=2.0"],
    #     "networks": ["pydantic[email]"],
    #     "phone": ["Jani-Common[locale]", "phonenumbers >=8.12.40"],
    #     "test": ["pytest >=6.2.5", "pytest-asyncio >=0.16.0"],
    #     "dev": ["Jani-Common[test]", "memory-profiler"],
    #     "all": [
    #         "Jani-Common[json,locale,moment,money,networks,phone]",
    #     ],
    # },
)
