#!/usr/bin/env python

from setuptools import setup, find_namespace_packages



setup(
    name="Jani",
    version="0.0.1",
    description="Jani",
    long_description="Tools, utilities and apps for django",
    author="David Kyalo, Qwertie LTD",
    author_email="kyalo@qwertie.com",
    classifiers=[],
    packages=find_namespace_packages(include=['jani.*']),
    include_package_data=True,
    python_requires="~=3.9",
    install_requires=[
        'arrow~=1.1.1',
        'cachetools~=4.2.1',
        'orjson>=3.5.2',
        'uvicorn>=0.13.4',
        'uvloop>=0.15.2',
        'blinker>=1.4',
    ],
    extras_require={
        'django': ['django~=3.2.4', 'django-ninja>=0.12.3'],
        'phonenumbers': ['phonenumbers>=8.12.24',],
    }
)
