from functools import cache

from djx.common.utils import setdefault, getitem
from djx.common.imports import ModuleImportRef


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



@cache
def app_is_installed(module_name):
    if ModuleImportRef(module_name)(None):
        from . import settings
        if apps := getitem(settings, 'INSTALLED_APPS', None):
            return module_name in apps
        return True
    return False

