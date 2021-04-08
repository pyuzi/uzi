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
    python_requires="~=3.8",
    install_requires=[
        'django~=3.1.7',       
        'cachetools~=4.2.1',
        # 'django-mptt~=0.12.0',
    ],
)
