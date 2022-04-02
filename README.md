# XDI

A super fast dependency injection library for python.



## Why use dependency injection?

Take a look at the following code.

```python
import os

class ApiClient:

    def __init__(self):
        self.api_url = os.getenv("API_URL")  # a dependency
        self.api_key = os.getenv("API_KEY")  # a dependency

    def get(self, path: str, *, token: str):
        return { url: f'{self.api_url}/{path}', status: 'ok', data: [] }



class Service:

    def __init__(self):
        self._api_client = ApiClient()  # a dependency
        # do some init

    def do_something(self):
        res = self._api_client.get('abc')
        print("Service doing something")


def some_func() -> None:
    service = Service()  # a dependency
    service.do_something()
    print("serivce has done something")


if __name__ == "__main__":
    some_func()

```

This code will run as expected. However:-

1. **Testing it will be difficult**
    
    For example, to test `Service` we need a fake `ApiClient` as we don't what to 
    make real api calls or might not have the credentials to do so. 
    Since `Service` creates it's own `ApiClient` instance, it is impossible to 
    safely mock the `ApiClient` for tests. 

2. **Lacks flexibility and extensibility**

    It's imppossible to create an additional `ApiClient` instance that uses a 
    different `API_URL` and/or `API_KEY`.



So what do we do? We should decouple our objects from their dependencies. 

That is, objects should not create each other anymore. They should provide a way 
to inject the dependencies instead.


Here's how.

```python

class ApiClient:

    def __init__(self, api_url: str, api_key: str): # we let the caller provide the dependencies
        self.api_url = api_url  
        self.api_key = api_key


class Service:

    def __init__(self, api_client: ApiClient): # we let the caller provide the dependency
        self._api_client = api_client 


def some_func(service: Service): # we let the caller provide the dependency
    service.do_something()
    print("serivce has done something")

```

Congratulations, your code is now loosely coupled. 

But remember, with freedom comes more responsibility.

The responsibility is left to the "caller" who has to know, assemble and provide the dependencies.

```python
some_func(
    service=Service(
        api_client=ApiClient(
            api_key=os.getenv("API_KEY"),
            api_url=os.getenv("TIMEOUT"),
        ),
    ),
)

```
This quickly becomes a problem when you what to use `some_func()` from multiple places.
Duplicating the assembly code with make it harder to change in the future.




### With XDI.


```python
from xdi import Injector, inject, context

@inject  # tell the di to inject dependencies
def some_func(service: Service):
    service.do_something()


injector = Injector()

# register the ApiClient
injector.factory(
    ApiClient, 
    api_url=os.getenv("API_URL"), # <-- provide value from env
    api_key=os.getenv('API_KEY')  # <-- provide value from env
).singleton()  # <-- make it provide only one instance.


# Register the Service. 
injector.factory(Service) 
# Since we did not specify a value for api_client. `ApiClient` will get injected 
# as it matches the type annotation `api_client: ApiClient`


# Run the injector
injector.run_forever()

some_func() # <-- dependency `Service` is injected automatically

```



## Installation

Install from [PyPi](https://pypi.org/project/xdi/)

```
pip install xdi
```


## Documentation

Coming soon.


## Production

__This package is still in active development and should not be used in production environment__

