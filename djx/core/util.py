from functools import cache

from djx.common.utils import setdefault


@cache
def is_django():
    try:
        from django.conf import settings
        from django.core.exceptions import ImproperlyConfigured
    except ImportError:
        return False

    try:
        bool(settings)
    except ImproperlyConfigured:
        return False
    else:
        
        return True



def django_settings():
    if not is_django():
        return
    return _load_django_settings()



@cache
def _load_django_settings():
    from django.conf import settings
    setdefault(settings, 'IS_SETUP', False)
    return settings




