# Laza DI

A super fast dependency injection library for python.


```python

from laza.di import Container

ioc = Container()


@ioc.injectable()
class A(object):
    ...


@ioc.injectable(shared=True)
class B(object):
    ...


# Register 
@ioc.injectable()
class C(object):
    def __init__(self, a: A, b: B): # <-- dependencies `A` and `B` are injected automatically
        self.a = a
        self.b = b


@ioc.injectable()
class Service(object):
    def __init__(self, a: A, b: B, c: C):
        self.a = a
        self.b = b
        self.c = c


@ioc.inject
def main(service: Service):
    ...


if __name__ == "__main__":

    main()  # <-- dependency is injected automatically

    # transient dependencies always resolve to a new values
    assert ioc[A] is not ioc[A] is not ioc[A]
    
    # Shared dependencies always resolve to the same value.
    assert ioc[B] is ioc[B] is ioc[B]
    assert ioc[Service] is ioc[Service] is ioc[Service]

```



## Installation

Install from [PyPi](https://pypi.org/project/laza-di/)

```
pip install laza-di
```


## Documentation

Coming soon.


## Production

__This package is still in active development and should not be used in production environment__


<!--
What describes a good DI container#
A good DI container:

* __must not__ be a Service Locator, and that’s easier to get as one might think, just go back to my previous post about this topic
* __must not__ be configurable globally (as a globally available instance), because it introduces problems with the reconfiguration
* __must support__ shared dependencies, so we wouldn’t need to exploit the Singleton Pattern
* __must support__ use of profiles, so we can configure it accordingly on different environments
* __should support__ the Decorator Pattern


## Modularity
The ability to isolate deps within their modules/packages

-->