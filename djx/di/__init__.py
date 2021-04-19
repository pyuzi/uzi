
default_app_config = f'{__package__}.apps.DefaultApp'



from .symbols import *
from .inspect import *
from .providers import *
from .injectors import *
from .scopes import head 
from .scopes import * 

from . import abc

# def __getitem__(key: abc._T_Injectable) -> abc._T_Injected:
#     return head()[key]