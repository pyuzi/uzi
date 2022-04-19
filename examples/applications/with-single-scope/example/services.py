"""Services module."""

from abc import ABC, abstractmethod
from contextlib import AbstractContextManager
import logging
import sqlite3
from typing import Dict

from mypy_boto3_s3 import S3Client


class DatabaseConnection(AbstractContextManager):

    @abstractmethod
    def execute(self, query): 
        ...



class BaseService:

    def __init__(self) -> None:
        self.logger = logging.getLogger(
            f"{__name__}.{self.__class__.__name__}",
        )


class UserService(BaseService):

    def __init__(self, db: DatabaseConnection) -> None:
        self.db = db
        super().__init__()

    def get_user(self, email: str) -> Dict[str, str]:
        assert email is not None
        self.logger.debug("User '%s' has been found in database", email)
        return {"email": email, "password_hash": "..."}




class AuthService(BaseService):

    def __init__(self, db: DatabaseConnection, token_ttl: int) -> None:
        self.db = db
        self.token_ttl = token_ttl
        super().__init__()

    def authenticate(self, user: Dict[str, str], password: str) -> None:
        assert password is not None
        self.logger.debug(
            "User '%s' has been successfully authenticated",
            user["email"],
        )



class PhotoService(BaseService):

    def __init__(self, db: DatabaseConnection, s3: S3Client) -> None:
        self.db = db
        self.s3 = s3
        super().__init__()

    def upload_photo(self, user: Dict[str, str], photo_path: str) -> None:
        self.logger.debug(
            "Photo %s has been successfully uploaded by user %s",
            photo_path,
            user["email"],
        )
