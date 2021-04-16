from flex.utils.proxy import CachedImportProxy

default_app_config = f'{__package__}.apps.DefaultApp'



registry = CachedImportProxy(f'{__package__}.reg:registry')


from .symbols import *
from .inspect import *
from .providers import *
