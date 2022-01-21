from pprint import pprint
from types import GenericAlias
import typing as t
import inspect as ins
import pytest
from functools import wraps

from laza.di import providers_new as p, IocContainer, InjectionToken






xfail = pytest.mark.xfail
parametrize = pytest.mark.parametrize



class ObjectProviderTests:


    def test_basic(self, ioc: IocContainer):
        tk = InjectionToken[str]('key')
        pr = p.Object(tk, 'The Provided object here.')
        ioc.register(tk, pr)

        inj = ioc.injector
        res = pr(inj.scope, tk)

        print(f'{pr.uses=} {res(inj).value=!r}')
        pprint(p.Union.__dataclass_fields__, indent=2, sort_dicts=False, depth=8)

        assert 0


