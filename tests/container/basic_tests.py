from types import GenericAlias
import typing as t
import inspect as ins
import pytest
from functools import wraps

from laza.di import IocContainer, Injector, InjectionToken





xfail = pytest.mark.xfail
parametrize = pytest.mark.parametrize

_T_Foo = t.TypeVar('_T_Foo', int, float)
_T_Bar = t.TypeVar('_T_Bar', str, bytes)
# _T_Baz = t.TypeVar('_T_Baz', float, int, str, bytes)
_T_Baz = t.TypeVar('_T_Baz', 'Foo', 'Bar', covariant=True)



class Foo(t.Generic[_T_Foo]):

    foo: _T_Foo

    def __init__(self, foo: _T_Foo=0.01, inj: Injector=None) -> None:
        self.foo = foo
        
class Bar(t.Generic[_T_Bar]):

    bar: _T_Bar

    def __init__(self, *, foo: Foo, bar: _T_Bar=None) -> None:
        self.bar = bar


class FooBar(Foo[_T_Foo], Bar[_T_Bar]):

    def __init__(self, foo: _T_Foo, bar: _T_Bar) -> None:
        self.foo = foo
        self.bar = bar


class IntFoo(Foo[int]):
    ...


class Baz:

    baz: tuple[_T_Baz]

    def __init__(self, *baz: _T_Baz) -> None:
        self.baz = baz



class FooBarBaz(Foo[float], Bar[str], t.Generic[_T_Baz]):

    # def __init__(self, foo: float, bar: str, baz: _T_Baz) -> None:
    #     self.foo = foo
    #     self.bar = bar
    #     self.baz = baz

    @wraps(Bar.__init__, assigned=('__doc__',), updated=('__annotations__',))
    def __init__(self, baz: Baz, **kwds: _T_Baz) -> None:
        self.foo = kwds['foo']
        self.bar = kwds['bar']
        self.baz = baz


class Scope:
    main = 'main'
    local = 'local'
    context = 'context'


class Scope:
    MAIN = 0
    LOCAL = 1




class BasicContainerTests:


    def test_scope_name(self):
        ioc = IocContainer('main', scope_aliases=dict(abc='local', xyz='abc')) 

        assert ioc.scope_name('main') == 'main'
        assert ioc.scope_name('abc') == 'local'
        assert ioc.scope_name('xyz') == 'local'

    def test_basic(self):
        ioc = IocContainer() 

        ioc.type(Foo, Foo, args=('FooMe',))
        ioc.type(Bar, Bar)

        assert ioc.make(Injector)

        assert ioc.is_provided(Foo)
        assert ioc.is_provided(Bar)

        assert isinstance(ioc.make(Foo), Foo)
        assert isinstance(ioc.make(Bar), Bar)
        # assert ioc.make(IntFoo, 222)

        print(ioc[list[Foo, Bar]])
        assert isinstance(ioc[t.Union[FooBarBaz, Bar]], Bar)
        assert isinstance(ioc[t.Union[FooBarBaz, Foo, Bar]], Foo)
        assert ioc[t.Union[FooBarBaz, FooBar, None]] is None

        # assert 0, '\n'
 
    def _test_list(self):
        from inspect import signature
        ioc = IocContainer() 

        print(f'[{Foo.__name__}] {signature(Foo)=!r}')
        print(f'[{Bar.__name__}] {signature(Bar)=!r}')
        print(f'[{FooBarBaz.__name__}] {signature(FooBarBaz)=!r}')

        ioc.type(Foo, Foo, args=('FooMe',))
        ioc.type(Bar, Bar)
        ioc.type(Baz, Baz)
        ioc.type(FooBarBaz, FooBarBaz)

        assert ioc.make(Injector)

        assert ioc[Baz]
        assert ioc[FooBarBaz]

        assert ioc.is_provided(Foo)
        assert ioc.is_provided(Bar)

        assert isinstance(ioc.make(Foo), Foo)
        assert isinstance(ioc.make(Bar), Bar)

        assert isinstance(ioc[t.Union[FooBarBaz, Bar]], Bar)
        assert isinstance(ioc[t.Union[FooBarBaz, Foo, Bar]], Foo)
        assert ioc[t.Union[FooBarBaz, FooBar, None]] is None

        # assert 0, '\n'
 
            
                 
    def test_speed(self, speed_profiler):
        from threading import local
        from contextvars import ContextVar

        

        class Object:
            val = 0
            # __locked__ = True
            _lock_ctx: ContextVar[bool]

            def __init__(self) -> None:
                object.__setattr__(self, '_lock_ctx', ContextVar('_lock_ctx', default=False))
                self.lock()

            @property
            def __locked__(self):
                return self._lock_ctx.get(False)

            def lock(self):
                # object.__setattr__(self, '__locked__', True)
                object.__setattr__(self, '_lock_token', self._lock_ctx.set(True))
                
                return self

            def unlock(self):
                # object.__setattr__(self, '__locked__', False)
                self._lock_ctx.reset(self._lock_token)
                return self

            def __setattr__(self, name: str, val) -> None:
                if self.__locked__:
                    raise AttributeError(f'{name!r}. {self.__class__.__name__} is locked.')
                super().__setattr__(name, val)
                
            def __iter__(self):
                yield self.unlock()
                return self.lock()
            
            def __enter__(self):
                return self.unlock()
            
            def __exit__(self, *exc):
                self.lock()



        class wlocal:

            def __enter__(self):
                return self
            
            def __exit__(self, *exc):
                pass
            

        loc = local()
        woc = wlocal()
        woc.val = loc.val = 0

        obj = Object()
        gen = Object()


        ctx = ContextVar('ctx', default=0)


        def fobj():
            nonlocal obj
            obj.unlock()
            prev = obj.val
            obj.val = prev + 1
            obj.lock()
            return obj.val

        def floc():
            prev = loc.val
            loc.val = prev + 1
            return loc.val

        def fvar():
            prev = ctx.get(0)
            token = ctx.set(prev + 1)
            return ctx.get()


        def fctx():
            nonlocal obj
            with obj as o:
                prev = o.val
                o.val = prev + 1
                return o.val

        def fgen():
            nonlocal obj
            gen = iter(obj)
            o = next(gen)
            # for obj in obj:
            prev = o.val
            o.val = prev + 1
            next(gen, ...)
            return o.val



        _n = int(5e5)


        profile = speed_profiler(_n, labels=('OBJ', 'CTX'))
        profile(fobj, fctx, '')

        profile = speed_profiler(_n, labels=('GEN', 'OBJ'))
        profile(fgen, fobj, '')

        profile = speed_profiler(_n, labels=('CTX', 'GEN'))
        profile(fctx, fgen, '')

       
        print(f'{fobj()=:,} --> {fctx()=:,} --> {fgen()=:,}')


        # print(f'\n => {injector[Foo]=}\n => {injector[Bar]=}\n => {injector[Bar]=}\n => {injector[Baz]=}\n => {injector[Scope["main"]]=}\n => {injector[INJECTOR_TOKEN]=}\n\n {pro()=}\n')

        # print('\n', *(f' - {k} --> {v!r}\n' for k,v in injector.content.items()))

        # assert injector[Bar] is not injector[Bar]


        # fp.close()

        assert 0


    