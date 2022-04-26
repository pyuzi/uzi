
# Factory Provider


The `Factory` provider creates new objects every time it's requested.


```python linenums="1" hl_lines="8 10"
from xdi import Container, providers

class Service:
    ...

container = Container()

container.factory(Service)
# or manually create the provider
container[Service] = providers.Factory(Service)
```
