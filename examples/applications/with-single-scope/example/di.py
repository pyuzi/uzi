"""Containers module."""

from inspect import Parameter, Signature
import logging.config
from pathlib import Path
import sqlite3

import boto3

from mypy_boto3_s3 import S3Client

from uzi import DepGraph, Dep
from uzi.containers import Container

from . import services
from .settings import Settings





ioc = Container()

ioc.factory(
    logging.config.fileConfig, 
    Path("logging.ini")
)


ioc.singleton(
    Settings,
    Settings.parse_ini_file, 
    Path('settings.ini')
)



ioc.singleton(
    services.DatabaseConnection,
    sqlite3.connect,
    Dep(Settings).lookup.database.dns
)


ioc.singleton(
        S3Client,
        boto3.client, 
        service_name="s3",
        aws_access_key_id=Dep(Settings).lookup.aws.access_key_id,
        aws_secret_access_key=Dep(Settings).lookup.aws.secret_access_key,
    )



ioc.factory(services.AuthService, token_ttl=Dep(Settings).lookup.auth.token_ttl)


ioc.provide(
    services.UserService,
    services.PhotoService,
)

