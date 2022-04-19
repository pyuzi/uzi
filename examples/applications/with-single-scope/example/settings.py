from configparser import ConfigParser, DEFAULTSECT
from pathlib import Path
import typing as t 

from pydantic import BaseSettings, BaseModel, SecretStr, Field


class DatabaseSettings(BaseModel, extra='allow'):

    dns: str = None


class AwsSettings(BaseModel):
    access_key_id: str = None
    secret_access_key: str = None


class AuthSettings(BaseModel):
    token_ttl: int = 3600



class Settings(BaseSettings, extra='allow'):
    aws: AwsSettings = Field(default_factory=AwsSettings)
    auth: AuthSettings = Field(default_factory=AuthSettings)
    database: DatabaseSettings = Field(default_factory=DatabaseSettings)
    
    @classmethod
    def parse_ini_file(cls, file: Path):
        parser = ConfigParser()
        parser.read(file)
        return cls.parse_obj(parser)
