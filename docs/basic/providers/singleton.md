# Singleton Provider

The `Singleton` provider creates and provides single object. 
It memorizes the first created object and returns it on the rest of the calls.


```py linenums="1" hl_lines="8 10"
from uzi import Container, providers

class Service:
    ...

container = Container()

container.singleton(Service)
# or manually create the provider
container[Service] = providers.Singleton(Service)
```
