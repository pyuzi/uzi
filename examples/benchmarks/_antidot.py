from antidote import inject, service, Constants, wire, Inject

from _bench import ALL_DEPS, SINGLETON_DEPS


LABEL = 'antidote'


@service(singleton=False)
class Foo:
    def __init__(self) -> None:
        pass

    
@service(singleton=False)
class Bar:

    def __init__(self, foo: Inject[Foo]) -> None:
        assert isinstance(foo, Foo)


@service(singleton=False)
class Baz:   

    def __init__(self, bar: Inject[Bar]) -> None:
        assert isinstance(bar, Bar)



@service(singleton=True)
class FooBar:
    
    def __init__(self, foo: Inject[Foo], bar: Inject[Bar]) -> None:
        assert isinstance(foo, Foo)
        assert isinstance(bar, Bar)


@service(singleton=True)
class FooBarBaz:
    
    def __init__(self, foo: Inject[Foo], bar: Inject[Bar], baz: Inject[Baz]) -> None:
        assert isinstance(foo, Foo)
        assert isinstance(bar, Bar)
        assert isinstance(baz, Baz)

  


@service(singleton=False)
class Service:
    
    def __init__(self, foo: Inject[Foo], bar: Inject[Bar], baz: Inject[Baz], foobar: Inject[FooBar], foobarbaz: Inject[FooBarBaz]) -> None:
        assert isinstance(foo, Foo)
        assert isinstance(bar, Bar)
        assert isinstance(baz, Baz)
        assert isinstance(foobar, FooBar)
        assert isinstance(foobarbaz, FooBarBaz)
   


def get_runner(cls):
    return globals()[cls.__name__]


