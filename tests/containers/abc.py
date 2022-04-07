from os import name
import typing as t
import pytest




from xdi.containers import Container
from xdi import Scope
from xdi._common.functools import uniqueid




xfail = pytest.mark.xfail
parametrize = pytest.mark.parametrize



_T = t.TypeVar('_T')
_Ta = t.TypeVar('_Ta')
_Tb = t.TypeVar('_Tb')
_Tc = t.TypeVar('_Tc')
_Tx = t.TypeVar('_Tx')




class ContainerTestCase:

    cls: t.ClassVar[type[Container]] = Container

    @pytest.fixture
    def make(self):
        yield self.cls

    @pytest.fixture
    def scope(self, scope: Scope):
        # for t_ in (_Ta, _Tb, _Tc):
        #     scope.value(t_, f'{uniqueid[t_]()}.00-scope-{scope.name}')
        return scope

    def _test_multi_providers(self, make: type[Container], scope: Scope):
        container = make()
        for _ in range(1,4):
            container = make(name=f'container[{_}]')
            for t_ in (_Ta, _Tb, _Tc):
                pro = container.value(t_, f'{uniqueid[t_]()}.X1-{container.name}')
                pro = container.value(t_, f'{uniqueid[t_]()}.X2-{container.name}')
                # if _ == 1:
                #     pro.final()
                # else:
                #     pro.default()
                    
                # container.value(t_, f'{uniqueid[t_]()}.02-{container.name}')
            scope.require(container)
            for _ in range(1,2):
                _container = make(name=f'{container.name}[{_}]')
                for t_ in (_Ta, _Tb, _Tc):
                    _container.value(t_, f'{uniqueid[t_]()}.XX-{_container.name}') #.default()
                container.require(_container)

        for t_ in (_Ta, _Tb, _Tc):
            scope.value(t_, f'{uniqueid[t_]()}.00-scope-{scope.name}').default()

        scope._boot()
        for t_ in (_T, _Ta, _Tb, _Tc):
            print(
                f' - {t_!r}', 
                *(f'   - {p!r}' for p in scope.registry.iall(t_)), 
                '='*80,
                f'  {scope.resolver.resolve(t_)!r}',
                '='*80,
                sep="\n  ")

        assert 0

        
    

