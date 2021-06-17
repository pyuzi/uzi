import django

from djx.di import di

from .handlers.asgi import ASGIHandler


def get_asgi_application():
    """DI ready public interface to Django's ASGI support. 
    Return an ASGI 3 callable that runs in a `request` injector scope. 
    """
    django.setup(set_prefix=False)
    return di.injector.make(ASGIHandler)

