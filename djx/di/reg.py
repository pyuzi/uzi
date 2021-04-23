from functools import partial
from collections import defaultdict
from itertools import chain
from flex.utils.decorators import export


from . import abc


_T_Scope = abc._T_Scope

__all__ = [

]

class _ScopeDefaultdict(defaultdict[str, _T_Scope]):
    """_ScopeDefaultdict Object"""
    def __init__(self, *args, **kwargs):
        super().__init__(None, *args, **kwargs)
    
    def __missing__(self, key) -> _T_Scope:
        from .scopes import Scope
        return Scope(key)


@export()
class Registry:

    all_providers: defaultdict[str, abc.PriorityStack]
    scope_types: abc.PriorityStack[str, type[abc.Scope]]
    # scopes: _ScopeDefaultdict[_T_Scope]

    def __init__(self):
        self.all_providers = defaultdict(abc.PriorityStack)
        self.scope_types = abc.PriorityStack()
    
    def add_provider(self, provider: abc.Provider, scope: str = None):
        self.all_providers[scope or provider.scope][provider.abstract] = provider
    
    def add_scope(self, cls: type[abc.Scope]):
        self.scope_types[cls.config.name] = cls

    def get_scope(self, name: str) -> abc.Scope:
        return self.scopes[name]
    

    # def collect_providers(self, scope: _T_Scope, *embeds: _T_Scope):
    #     # reg = self.all_providers
    #     embeds
    #     provs = chain(*(a.providers.values() for a in embeds))
    #     if scope != abc.ANY_SCOPE:
    #         embeds = (abc.ANY_SCOPE,) + embeds + (scope,)
            
    #     else:
    #         provs = reg[scope].values()
        
    #     return defaultdict(lambda: None, ((p.abstract(), p) for p in provs))

    # def _create_scope(self, name: str):
    #     from .scopes import ImplicitScope, ScopeType

    #     if name in self.scope_types:
    #         return self.scope_types[name]()
    #     elif name in self.all_providers:
    #         return ScopeType(name, (ImplicitScope,), {})
        
    #     raise KeyError(f'Scope not defined: {name}')

        

registry = Registry()



