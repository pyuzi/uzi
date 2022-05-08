
from functools import cache
from typing import Union
from uzi import Container, DepGraph


from _benchmarkutil import Benchmark, Timer
from uzi.injectors import Injector




class Foo:
     def __init__(self) -> None:
        pass

    
class Bar:
    
    def __init__(self, foo: Foo, /) -> None:
        assert isinstance(foo, Foo)

     
class Baz:   
    def __init__(self, bar: Bar, /) -> None:
        assert isinstance(bar, Bar)


 
class FooBar:
    
    def __init__(self, foo: Foo, bar: Bar, /) -> None:
        assert isinstance(foo, Foo)
        assert isinstance(bar, Bar)



class FooBarBaz:
    
    def __init__(self, foo: Foo, bar: Bar, baz: Baz, /) -> None:
        assert isinstance(foo, Foo)
        assert isinstance(bar, Bar)
        assert isinstance(baz, Baz)
    



class Service:
    
    def __init__(self, foo: Foo, bar: Bar, baz: Baz, /, *, foobar: FooBar, foobarbaz: FooBarBaz) -> None:
        assert isinstance(foo, Foo)
        assert isinstance(bar, Bar)
        assert isinstance(baz, Baz)
        assert isinstance(foobar, FooBar)
        assert isinstance(foobarbaz, FooBarBaz)



ioc = Container() 

ioc.factory(Foo)
ioc.factory(Bar)
ioc.factory(Baz)
ioc.singleton(FooBar)
ioc.singleton(FooBarBaz)
ioc.factory(Service)


# @inject
# def inject_1(baz: Baz, /):
#     assert isinstance(baz, Baz)
#     return baz

# @inject
# def inject_2(foo: Foo, bar: Bar, baz: Baz):
#     assert isinstance(foo, Foo)
#     assert isinstance(bar, Bar)
#     assert isinstance(baz, Baz)
#     return foo, bar, baz

# @inject
# def inject_3(foobar: FooBar, foobarbaz: FooBarBaz, /, service: Service):
#     assert isinstance(foobar, FooBar)
#     assert isinstance(foobarbaz, FooBarBaz)
#     assert isinstance(service, Service)
#     return foobar, foobarbaz, service



_tap = lambda x=True: x and None
mkfoo = lambda: Foo()
mkbar = lambda: Bar(mkfoo())
mkbaz = lambda: Baz(mkbar())
mkfoobar = lambda: FooBar(mkfoo(), mkbar())
mkfoobarbaz = lambda: FooBarBaz(mkfoo(), mkbar(), mkbaz())
mkservice = lambda: Service(mkfoo(), mkbar(), mkbaz(), foobar=mkfoobar(), foobarbaz=mkfoobarbaz())

# mkinject_1 = lambda: inject_1.__wrapped__(mkbaz())
# mkinject_2 = lambda: inject_2.__wrapped__(mkfoo(), mkbar(), mkbaz())
# mkinject_3 = lambda: inject_3.__wrapped__(mkfoobar(), mkfoobarbaz(), mkservice())

_n = int(5e3)

with Timer() as tm:
    scp = DepGraph(ioc)
    inj = Injector(scp)

    bfoo = Benchmark('Foo.', _n).run(py=mkfoo, uzi=inj.bound(Foo))
    bbar = Benchmark('Bar.', _n).run(py=mkbar, uzi=inj.bound(Bar))
    bbaz = Benchmark('Baz.', _n).run(py=mkbaz, uzi=inj.bound(Baz))
    print(bfoo, bbar, bbaz, sep='\n')
    # bench = Benchmark(str(Union[Foo, Bar, Baz]), _n)
    # bench |= bfoo | bbar | bbaz 
    # print(bench, '\n')


    bfoobar     = Benchmark('FooBar.', _n).run(py=mkfoobar, uzi=inj.bound(FooBar))
    bfoobarbaz  = Benchmark('FooBarBaz.', _n).run(py=mkfoobarbaz, uzi=inj.bound(FooBarBaz))
    bservice    = Benchmark('Service.', _n).run(py=mkservice, uzi=inj.bound(Service))

    print('', bfoobar, bfoobarbaz, bservice, sep='\n')

    # bench = Benchmark(str(Union[FooBar, FooBarBaz, Service]), _n)
    # bench |= bfoobar | bfoobarbaz | bservice
    # print(bench, '\n')

    # binject_1 = Benchmark('inject_1.', _n).run(py=mkinject_1, uzi=inject_1)
    # binject_2 = Benchmark('inject_2.', _n).run(py=mkinject_2, uzi=inject_2)
    # binject_3 = Benchmark('inject_3.', _n).run(py=mkinject_3, uzi=inject_3)


    # bench = Benchmark('INJECT', _n)
    # bench |= binject_1 | binject_2 | binject_3
    # print(bench, '\n')
        

print(f'TOTAL: {tm}')

