from email.policy import default
from unittest.mock import Mock
import pytest
from inspect import Parameter




from laza.di.providers.functools import FactoryResolver, _EMPTY
from laza.di import Inject


from libs.common.laza.common.collections import Arguments
from libs.di.laza.di.injectors import Injector


xfail = pytest.mark.xfail
parametrize = pytest.mark.parametrize




class FactoryResolverTests:

    cls = FactoryResolver
    
    @parametrize(['fn', 'args', 'kwds', 'exp'], [
        (lambda a, b, c: ..., ('A', 'B', 'C'), {}, dict(a='A', b='B', c='C')),
        (lambda a, b, c: ..., (), dict(a='A', b='B', c='C'), dict(a='A', b='B', c='C')),
        (lambda x, *p, k, **kw: ..., ('X', 1, 2), dict(k='K', y='Y', z='Z'), dict(x='X', p=(1,2), k='K', kw=dict(y='Y', z='Z'))),
    ])
    def test_arguments(self, fn, args, kwds, exp):
        res = self.cls(fn, arguments=Arguments(args, kwds))
        assert res.arguments == exp
        
        
    def test_call(self, injector: Injector):
        
        def foo(obj: object, a: int=1, *, k=Inject(str), kw: list):
            return obj, a, k, kw

        vals = object(), 11, 'The K', [1,2,3]

        res = self.cls(foo, arguments=Arguments.make(a=vals[1]))        
        ctx = { 
            object: lambda: vals[0], 
            Inject(str): lambda: vals[2], 
            list: lambda: vals[3], 
        }
        
        injector.is_provided = Mock(side_effect=lambda o: o in ctx)


        rfn, deps = res(injector, foo)
        assert callable(rfn)
        assert deps == {object: ['obj'], list: ['kw'], Inject(str): ['k']}
        fn = rfn(ctx)
        assert callable(fn)
        v = fn()
        assert v == vals