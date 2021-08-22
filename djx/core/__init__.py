from functools import cache
from djx.common.imports import ImportRef
from djx.common.proxy import proxy
from djx.di import di

default_app_config = f'{__package__}.apps.djx.DjxApp'


version = (0, 0, 1)

__version__ = ".".join(map(str, version))



from .abc import settings

