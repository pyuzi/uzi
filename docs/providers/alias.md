# Alias Provider

Used to "alias" another existing dependency. 


```python linenums="1" hl_lines="9 11"
import typing as t
from xdi import Container, providers

_Ta = t.TypeVar('_Ta') 
_Tb = t.TypeVar('_Tb') 

container = Container()

container[_Ta] = providers.Alias(_Ta)
# or use the helper method
container.alias(_Tb, _Ta)

obj = object()
# bind `_Ta` to object `obj`
container.value(_Ta, obj) 
```

In the above snippet, dependents of both `_Tb` and `_Ta` will be provided with `obj`.

### Use Case

```python
import typing as t
from xdi import Container, providers

_Ta = t.TypeVar('_Ta') 
_Tb = t.TypeVar('_Tb') 


class Cache:
    ...

class DbCache(Cache):
    ...

class MemoryCache(Cache):
    ...
    
class RedisCache(Cache):
    ...


container = Container()

container.singleton(DbCache)
container.singleton(RedisCache)
container.singleton(MemoryCache)

container.alias(Cache, RedisCache)
```

