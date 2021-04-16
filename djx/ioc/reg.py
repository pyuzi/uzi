
from collections import defaultdict
from typing import TypeVar

from flex.utils.decorators import export


from . import abc
from .symbols import symbol
from .providers import ProviderStack, Provider, has_provider


__all__ = [

]


_T = TypeVar('_T')
_I = TypeVar('_I', bound=abc.Injectable)




@export()
class Registry:

    providers: defaultdict[symbol[_I], ProviderStack]
    contexts: defaultdict[symbol[_I], ProviderStack]

    def __init__(self):
        self.providers = defaultdict(ProviderStack)
    
    def add_provider(self, provider: Provider, context: str = None):
        return self.providers[context or provider.context].push(provider)
    
    def add_context(self, context: type[abc.Context]):
        pass


        

registry = Registry()



