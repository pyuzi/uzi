import django


from djx.di import ioc
from .handlers.wsgi import WSGIHandler



def get_wsgi_application():
    """DI ready public interface to Django's WSGI support. 
    Return a WSGI callable that runs in a `request` injector scope. 
    """
    django.setup(set_prefix=False)
    return ioc.make(WSGIHandler)


def get_internal_wsgi_application():
    """DI ready public interface to Django's WSGI support. 
    Return a WSGI callable that runs in a `request` injector scope. 
    """
    from django.conf import settings
    try:
        rv = settings.WSGI_APPLICATION
    except AttributeError:
        rv = None
    finally:
        if rv is None:
            pass
