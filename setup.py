#!/usr/bin/env python

from setuptools import setup, find_namespace_packages


setup(
    name="django-extended",
    version="0.0.1",
    description="Django Extended",
    long_description="Tools, utilities and apps for django",
    author="David Kyalo, Qwertie LTD",
    author_email="kyalo@qwertie.com",
    classifiers=[],
    packages=find_namespace_packages(include=['djx.*']),
    include_package_data=True,
    python_requires="~=3.9",
    install_requires=[
        'cachetools~=4.2.1',
        'orjson>=3.5.2',
        'uvicorn>=0.13.4',
        'uvloop>=0.15.2',
    ],
    extras_require={
        'django': ['django~=3.1.7',],
        'phonenumbers': ['phonenumbers>=8.12.24',],
    }
)
