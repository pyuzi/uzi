from contextlib import nullcontext



import typing as t

from timeit import repeat

import pytest


from djx.di import ioc


from .mocks import *


xfail = pytest.mark.xfail
parametrize = pytest.mark.parametrize




class SymbolTests:

    def run_basic(self, obj, kind=None):
        return True

    # def test_basic(self):
    #     assert is_injectable(Foo)

    #     assert is_injectable(user_func_injectable)
    #     assert is_injectable(user_symb)
    #     assert is_injectable(user_symb())
    #     assert is_injectable(user_str)
    #     assert is_injectable(symbol(user_str))
    #     assert not is_injectable(noop_symb)
    #     assert not is_injectable(user_func_symb)

    def test_late_provider(self):
        @ioc.injectable(at='main')
        class Early:
            

            def __str__(self) -> str:
                return ''
        
        @ioc.injectable(at='main')
        class Late:
            pass


        with ioc.use('test') as inj:
            with inj.context:
                key = 'late'
                val ='This was injected late'
                assert inj.get(key) is None

                ioc.value(key, val)

                print('', *inj.scope.providers.maps, end='\n\n', sep='\n -><=')
                print('\n', *(f' -+= {k} --> {v!r}\n' for k,v in ioc.injector.content.items()))
        
                # vardump([(s,k) for s, d in ioc.providers.items() for k in d])
                assert isinstance(inj[Early], Early)

                assert inj[key] == val

                
                vardump({ s.name: s.resolvers for s in ioc.scopes.values() if s.resolvers })

                ioc.alias(Early, Late, at='main')
                assert isinstance(inj[Early], Late)

                ioc.alias(Late, key, at='main')
                assert inj[Early] == val

                vardump({ s.name: s.resolvers for s in ioc.scopes.values() if s.resolvers })

        assert 1
                
    def test_speed(self, speed_profiler):
        # with scope() as inj:
        with nullcontext():
            # with scope('local') as inj:
            # with inj.context:

            #     print('*'*16, inj,'*'*16)
            #     # with scope('abc') as _inj:
                #     nl = "\n    -- "
                with ioc.use('test') as inj:
                    with inj.context:
                        null = lambda: None
                        mkinj = lambda: ioc.injector
                        mkfoo = lambda: Foo(user_func_symb(), user=user_func_str(), inj=mkinj())
                        # mkfoo = lambda: Foo('a very simple value here', user=user_func_str(), inj=null())
                        mkbaz = lambda: Baz() 
                        mkfunc = lambda: user_func_injectable(user_func_str(), mkfoo())
                        mkbar = lambda: Bar(mkfoo(), mkfoo(), user_func_str(), mkfunc(), sym=user_func_symb(), baz=mkbaz())
                        injfoo = lambda: inj[Foo]
                        injfunc = lambda: inj[user_func_str]
                        injbar = lambda: inj[Bar]
                        injbafoo = lambda: inj[Bar].infoo
                        injbaz = lambda: inj[Baz]
                        inj404 = lambda: inj['404']

                        _n = int(5e4)

                        # injbar()
                        # injfoo()

                        profile = speed_profiler(_n, labels=('PY', 'DI'))
                    
                        profile(mkbaz, injbaz, 'Baz')
                        profile(mkfoo, injfoo, 'Foo')
                        profile(mkbar, injbar, 'Bar')

                
                        wrapbar = ioc.wrap(Bar, kwargs=dict(foo='PATCHED FOO', kw2='KEYWOARD_2'))
                        wrapfunc = ioc.wrap(user_func_str, kwargs=dict(p='PATCHED USER'))

                        print(f'\n WRAPPED ---> {wrapbar()!r}\n REAL   ---> {injbar()!r}')
                        print(f'\n WRAPPED ---> {wrapfunc()!r}\n REAL   ---> {injfunc()!r}')
                        
                        # print(f'\n => {injector[Foo]=}\n => {injector[Bar]=}\n => {injector[Bar]=}\n => {injector[Baz]=}\n => {injector[Scope["main"]]=}\n => {injector[INJECTOR_TOKEN]=}\n\n {pro()=}\n')

                        # print('\n', *(f' - {k} --> {v!r}\n' for k,v in injector.content.items()))

                        # assert injector[Bar] is not injector[Bar]


        assert 0
