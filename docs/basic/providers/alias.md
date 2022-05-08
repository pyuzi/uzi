# Alias Provider

Used to "alias" another existing dependency. 


```python linenums="1" title="Simple Usage" hl_lines="10 13"
--8<-- "examples/providers/alias/example_01.py"
```

In the above snippet, dependents of both `_Tb` and `_Ta` will be provided with `obj`.

### Use Case

```python
import typing as t
from uzi import Container, providers

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

