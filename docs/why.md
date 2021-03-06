
# Why Dependency Injection?

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


def some_func(*args, **kwargs) -> None:
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
        self.api_url, self.api_key = api_url, api_key
        

class Service:

    def __init__(self, api_client: ApiClient): # we let the caller provide the dependency
        self._api_client = api_client 


def some_func(*args, service: Service, **params): # we let the caller provide the dependency
    ...


```
Congratulations, your code is now loosely coupled. 

But remember, with freedom comes more responsibility.

The responsibility is left to the "caller" who has to know, assemble and provide the dependencies.

```python
some_func(
    *args, 
    service=Service(
        api_client=ApiClient(
            api_key=os.getenv("API_KEY"),
            api_url=os.getenv("TIMEOUT"),
        ),
    ),
    **kwargs, 
)

```
This quickly becomes a problem when you what to use `some_func()` from multiple places.
Duplicating the assembly code with make it harder to change in the future.




### With Uzi.

Simple DI using `uzi`'s low level API.

```python
from uzi import Injector, Scope, Container

container = Container()

# register the ApiClient
container.singleton(
    ApiClient, 
    api_url=os.getenv("API_URL"), # <-- provide value from env
    api_key=os.getenv('API_KEY')  # <-- provide value from env
)  # <-- make it provide only one instance.


# Register the Service. 
container.factory(Service) 
# Since we did not specify a value for api_client. `ApiClient` will get injected 
# as it matches the type annotation `api_client: ApiClient`

# Create the scope
scope = Scope(container)

# Create an injector
injector = Injector(scope)


# Use the injector to run `some_func`
result = injector.make(some_func, 'xyz', 23, **params) # <-- dependency `Service` is injected automatically

```

