"""Main module."""

import sys

from laza.di import inject, context, Dep

from .services import UserService, AuthService, PhotoService
from .di import injector
from .settings import Settings


@inject
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


if __name__ == "__main__":
    with context(injector) as ctx:
        main(*sys.argv[1:])
   
   