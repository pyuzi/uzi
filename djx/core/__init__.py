

default_app_config = f'{__package__}.apps.djx.DjxApp'


version = (0, 0, 1)

__version__ = ".".join(map(str, version))



from djx.abc import Settings
from djx.di import ioc
from .util import app_is_installed, django_settings


ioc.type(Settings, django_settings, at='main', cache=True)
settings: Settings = ioc.proxy(Settings, callable=True)