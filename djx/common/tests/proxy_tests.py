import pytest


from ..proxy import CachedProxy, CallableProxy, CachedCallableProxy, Proxy, WeakCallableProxy, WeakProxy, isproxy



xfail = pytest.mark.xfail
parametrize = pytest.mark.parametrize






class ProxyTests:

    def test_basic(self):

        class Foo:
            pass

        target = Foo()
        p = Proxy(lambda: target)

        assert isproxy(p)
        assert isproxy(type(p))
        assert not isproxy(target)
        assert p == target
        assert p.__proxy_target__ is target
        assert isinstance(p, Foo)
        assert isinstance(p, Proxy)

        p2 = Proxy(Foo, callable=True)
        p3 = Proxy(list, callable=True)
        
        assert isproxy(p2, CallableProxy)
        assert isinstance(p2, Foo)
        assert isinstance(p2(), Foo)
        assert type(p2()) is Foo
        assert p2 != Proxy(Foo)

    def test_cached(self):

        x = []
        def foo():
            x.append(len(x))
            return x.copy() # f'Foo value {len(x)}'
        

        p = Proxy(foo, cache=True)

        assert isproxy(p, CachedProxy)
        assert isinstance(p, type(foo()))
        assert p == p.__proxy_target__
        assert p.__proxy_target__ is p.__proxy_target__
        print(f'--> {type(p)}', p.__doc__)
        
        p2 = Proxy(foo, cache=True, callable=True)
        
        assert isproxy(p2, CachedCallableProxy)
        assert isinstance(p2, type(foo()))
        assert isinstance(p2(), type(foo()))
        assert type(p2()) is type(foo())
        assert p2 == p2()
        assert p2() is p2()

    def text_with_types(self):

        class Foo:
            
            def __init__(self, a=None) -> None:
                self.a = a

        p = Proxy(lambda:Foo)
        assert isproxy(p)
        assert isproxy(type(p))
        assert isinstance(p, type)
        assert issubclass(p, Foo)

        assert p == Foo
        assert p.__proxy_target__ is Foo
        assert isinstance(p(), Foo)
        assert type(p()) is type(Foo())
        assert p('aaa').a == 'aaa'

    
    def test_weak(self):

        class Foo:
            pass

        target = Foo()

        p = Proxy(lambda: target, weak=True, cache=True)

        assert isproxy(p, (WeakProxy, CachedProxy))
        assert p == target
        assert p.__proxy_target__ is target
        assert isinstance(p, Foo)
        assert isinstance(p, Proxy)
        assert isinstance(p, WeakProxy)
        assert isinstance(p, CachedProxy)

        p2 = Proxy(lambda: target, cache=True, callable=True, weak=True)
        
        assert isproxy(p2, WeakCallableProxy)
        assert isinstance(p2, type(target))
        assert isinstance(p2(), type(target))
        assert type(p2()) is type(target)
        assert p2 == p2()
        assert p2() is p2()
