from functools import partial
from collections import defaultdict
from itertools import chain
from flex.utils.decorators import export


from . import abc


_T_Scope = abc._T_Scope

__all__ = [

]

class _ScopeDefaultdict(defaultdict[str, type[_T_Scope]]):
    """_ScopeDefaultdict Object"""
    def __init__(self, *args, **kwargs):
        super().__init__(None, *args, **kwargs)
    
    def __missing__(self, key: str) -> _T_Scope:
        self[key] = registry._create_scope(key)
        return self[key]

        
@export()
class Registry:

    all_providers: defaultdict[str, abc.PriorityStack]
    scope_types: abc.PriorityStack[str, type[abc.Scope]]
    scopes: _ScopeDefaultdict[_T_Scope]

    def __init__(self):
        self.all_providers = defaultdict(abc.PriorityStack)
        self.scope_types = abc.PriorityStack()
        self.scopes = _ScopeDefaultdict()
    
    def add_provider(self, provider: abc.Provider, scope: str = None):
        self.all_providers[scope or provider.scope][provider.abstract] = provider
    
    def add_scope(self, cls: type[abc.Scope]):
        self.scope_types[cls.conf.name] = cls

    def collect_providers(self, scope, *aliases):
        reg = self.all_providers
        if scope != abc.ANY_SCOPE:
            aliases = (abc.ANY_SCOPE,) + aliases + (scope,)
            provs = chain(*(reg[a].values() for a in aliases if a in reg))
        else:
            provs = reg[scope].values()
        
        return defaultdict(lambda: None, ((p.abstract(), p) for p in provs))

    def _create_scope(self, name: str):
        return self.scope_types[name]()

    def get_scope(self, name: str) -> abc.Scope:
        return self.scopes[name]
    
        

registry = Registry()



