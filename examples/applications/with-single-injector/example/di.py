"""Containers module."""

from inspect import Parameter, Signature
import logging.config
from pathlib import Path
import sqlite3

import boto3

from mypy_boto3_s3 import S3Client

from xdi import Injector, Dep

from . import services
from .settings import Settings





injector = Injector()

injector.factory(logging.config.fileConfig, Path("logging.ini")).autoload()

injector.factory(Settings).singleton().using(
    Settings.parse_ini_file, 
    Path('settings.ini')
)



injector.resource(services.DatabaseConnection).using(
    sqlite3.connect,
    Dep(Settings).database.dns
)


injector.factory(S3Client).singleton().using(
        boto3.client, 
        service_name="s3",
        aws_access_key_id=Dep(Settings).aws.access_key_id,
        aws_secret_access_key=Dep(Settings).aws.secret_access_key,
    )



injector.factory(services.AuthService, token_ttl=Dep(Settings).auth.token_ttl)


injector.provide(
    services.UserService,
    services.PhotoService,
)

