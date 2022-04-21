# Value Provider

Provide given an object "as is".

```python linenums="1" hl_lines="9 11"
import typing as t
from xdi import Container, providers

_T_Str = t.TypeVar('_T_Str', str) 

container = Container()

# Will provide 'xyz' to the dependants of _T_Str
container[_T_Str] = providers.Value('xyz')
# or use the helper method 
container.value(_T_Str, 'abc') 
```

