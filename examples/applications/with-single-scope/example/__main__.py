"""Main module."""

import sys

from xdi import Injector, Scope

from .services import UserService, AuthService, PhotoService
from .di import ioc
from .settings import Settings


def main(
        email: str,
        password: str,
        photo: str,
        user_service: UserService,
        auth_service: AuthService,
        photo_service: PhotoService
) -> None:
    user = user_service.get_user(email)
    auth_service.authenticate(user, password)
    photo_service.upload_photo(user, photo)


scope = Scope(ioc)

if __name__ == "__main__":
    Injector(scope).make(main, *sys.argv[1:])
    
    