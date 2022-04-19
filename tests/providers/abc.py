from copy import copy, deepcopy
from inspect import isawaitable
from collections.abc import Callable, Sequence, MutableSequence, Set, MutableSet
import typing as t
from unittest.mock import Mock, patch
import pytest
from tests.conftest import Container


from xdi.providers import Provider
from xdi._dependency import Dependency
from xdi.scopes import Scope


from ..abc import BaseTestCase

xfail = pytest.mark.xfail
parametrize = pytest.mark.parametrize


_notset = object()

_T = t.TypeVar("_T")
_T_Pro = t.TypeVar("_T_Pro", bound=Provider, covariant=True)
_T_NewPro = Callable[..., _T_Pro]


class ProviderTestCase(BaseTestCase[_T_Pro]):

    type_: t.ClassVar[type[_T_Pro]] = Provider

    value = _notset
    
    @pytest.fixture
    def abstract(self):
        return _T

    @pytest.fixture
    def concrete(self):
        def fn(): ...
        return fn

    @pytest.fixture
    def new_args(self, concrete, new_args):
        return (concrete, *new_args)

    @pytest.fixture
    def value_factory(self):
        return lambda: object()

    @pytest.fixture
    def value_setter(self, value_factory):
        def fn(*a, **kw):
            self.value = val = value_factory(*a, **kw)
            return val
        return fn

    def test_basic(self, new: _T_NewPro, cls: type[_T_Pro]):
        subject = new()
        assert isinstance(subject, Provider)
        assert subject.__class__ is cls
        assert cls.__slots__ is cls.__dict__["__slots__"]
        return subject

    def test_copy(self, new: _T_NewPro):
        subject = new()
        cp = copy(subject)
        assert cp.__class__ is subject.__class__
        assert cp.concrete == subject.concrete
        assert cp == subject
        return subject, cp

    def test_deepcopy(self, new: _T_NewPro):
        subject = new()
        cp = deepcopy(subject)
        assert cp.__class__ is subject.__class__
        # assert cp == subject
        return subject, cp

    def test_compare(self, new: _T_NewPro):
        subject, subject_2 = new(), new()
        assert subject.__class__ is subject_2.__class__
        assert subject.concrete == subject_2.concrete
        assert subject == subject_2
        assert not subject != subject_2
        assert hash(subject) == hash(subject)
        return subject, subject_2

    def test_immutable(self, new: _T_NewPro, immutable_attrs):
        self.assert_immutable(new(), immutable_attrs)

    def test_set_container(self, mock_container, new: _T_NewPro):
        subject = new()
        assert subject.container is None
        assert subject.set_container(mock_container) is subject
        subject.set_container(mock_container)
        assert subject.container is mock_container
        return subject

    @xfail(raises=AttributeError, strict=True)
    def test_xfail_multiple_set_container(self, MockContainer, new: _T_NewPro):
        subject = new()
        assert subject.container is None
        subject.set_container(MockContainer()).set_container(MockContainer())
        return subject,

    def test_is_default(self, new: _T_NewPro):
        subject = new()
        subject.default()
        assert subject.is_default is True
        subject.default(False)
        assert subject.is_default is False
        return subject

    @xfail(raises=AttributeError, strict=True)
    @parametrize(
        ["op", "args"],
        [
            ("default", ()),
            ('when', ()),
            ("set_container", (None,)),
        ],
    )
    def test_xfail_frozen(self, new: _T_NewPro, op, args):
        subject = new()
        subject._freeze()
        fn = getattr(subject, op, None)
        assert fn
        fn(*args)
        return subject

    def test_use(self, new: _T_NewPro, concrete):
        subject = new()
        orig = subject.concrete
        mock = Mock(orig)

        assert subject.concrete is orig
        assert subject is subject.use(mock)
        assert subject.use()(mock) in (subject, mock)
        assert subject.concrete is mock

    def test_filters(self, new: _T_NewPro):
        subject = new()
        f0, f1, f2, f3 = (Mock(Callable, name=f'filter[{i}]') for i in range(4))
        
        assert subject.when(f1, f2, f0, f2) is subject
        assert tuple(subject.filters) == (f1, f2, f0)

        assert isinstance(subject.filters, (Set, Sequence))
        assert not isinstance(subject.filters, (MutableSet, MutableSequence))

        assert tuple(subject.when(f3, f1).filters) == (f1, f2, f0, f3)
        assert tuple(subject.when(f0, f1, replace=True).filters) == (f0, f1,)
        assert tuple(subject.when(replace=True).filters) == ()
        return subject

    def test_apply_filters(self, abstract, new: _T_NewPro, mock_scope: Scope):
        subject = new()
        
        f0, f1, f2, f3, f4 = (Mock(Callable, return_value=True, name=f'filter[{i}]') for i in range(5))

        subject.when(f0, f1, f2, f3, f4)
        assert tuple(subject.filters) == (f0, f1, f2, f3, f4)
        assert subject._apply_filters(abstract, mock_scope) is True
        for f in (f0, f1, f2, f3, f4):
            f.assert_called_once_with(subject, abstract, mock_scope)
            f.reset_mock()
        
        f2.return_value = False
        assert subject._apply_filters(abstract, mock_scope) is False
        
        for f in (f0, f1, f2,):
            f.assert_called_once_with(subject, abstract, mock_scope)

        for f in (f3, f4):
            f.assert_not_called()
        return subject

    def test_can_resolve(self, abstract, cls: type[_T_Pro], new: _T_NewPro, mock_scope: Scope, mock_container: Container):
        with patch.object(cls, '_can_resolve'):
            subject = new()
            subject._can_resolve.return_value = True
            f = Mock(Callable, return_value=True, name=f'filter')

            subject.when(f).set_container(mock_container)
            
            assert subject.can_resolve(abstract, mock_scope) is True
            f.assert_called_once_with(subject, abstract, mock_scope)
            assert subject.can_resolve(abstract, mock_scope) is True
            mock_scope.__contains__.assert_called_with(mock_container)

            f.reset_mock()
            f.return_value = False
            assert subject.can_resolve(abstract, mock_scope) is False
            f.assert_called_once_with(subject, abstract, mock_scope)
            assert subject.can_resolve(abstract, mock_scope) is False

            f.reset_mock()
            mock_scope.__contains__.return_value = False
            assert subject.can_resolve(abstract, mock_scope) is False
            subject._can_resolve.assert_called_with(abstract, mock_scope)

            return subject

    def test__can_resolve(self, abstract, new: _T_NewPro, mock_scope: Scope):
        subject = new()
        res = subject._can_resolve(abstract, mock_scope)
        assert res == subject.can_resolve(abstract, mock_scope)
        return subject, res

    def test_get_dependency_kwargs(self, new: _T_NewPro):
        subject = new()
        kwds = dict(_x__aGgYh0RdYvYa__x_=object(), _a_xRbYf78PxKsT4x_a_=object())
        res = subject._get_dependency_kwargs(**kwds)
        assert res['_x__aGgYh0RdYvYa__x_'] is kwds['_x__aGgYh0RdYvYa__x_'] 
        assert res['_a_xRbYf78PxKsT4x_a_'] is kwds['_a_xRbYf78PxKsT4x_a_'] 
        return subject
        

    @xfail(raises=NotImplementedError, strict=False)
    def test_make_dependency(self, cls: type[_T_Pro], abstract, mock_scope: Scope, new: _T_NewPro):
        orig = cls._get_dependency_kwargs
        with patch.object(cls, '_get_dependency_kwargs', wraps=lambda *a, **kw: orig(subject, *a, **kw)):
            subject = new()
            dep = subject._make_dependency(abstract, mock_scope)
            assert isinstance(dep, Dependency)
            subject._get_dependency_kwargs.assert_called_once()
            return subject, dep

    def test_resolve(self, cls: type[_T_Pro], abstract, new: _T_NewPro, mock_scope: Scope):
        subject = new()
        res = subject.resolve(abstract, mock_scope)
        assert isinstance(res, Dependency)
        assert subject._frozen
        return subject, res    

    def test_resolve_calls__resolve(self, cls: type[_T_Pro], abstract, new: _T_NewPro, mock_scope: Scope):
        with patch.object(cls, '_resolve'):
            subject = new()
            res = subject.resolve(abstract, mock_scope)
            subject._resolve.assert_called_once_with(abstract, mock_scope)  
            return subject, res    

    def test_resolve_calls__resolve(self, cls: type[_T_Pro], abstract, new: _T_NewPro, mock_scope: Scope):
        with patch.object(cls, 'can_resolve'):
            subject = new()
            subject.can_resolve.return_value = True
            res = subject.resolve(abstract, mock_scope)
            subject.can_resolve.assert_called_once_with(abstract, mock_scope)        
            return subject, res    

    async def test_inject(self, cls: type[_T_Pro], abstract, new: _T_NewPro, mock_scope: Scope, mock_injector):
        subject = new()
        dep = subject.resolve(abstract, mock_scope)
        assert isinstance(dep, Dependency)
        func = dep.bind(mock_injector)
        assert callable(func)
        res = func()
        if dep.is_async:
            assert isawaitable(res)
            res = await res
        return subject, res    



class AsyncProviderTestCase(ProviderTestCase):

    @pytest.fixture
    def value_factory(self):
        async def fn():
            return object()

        return fn

    @pytest.fixture
    def value_setter(self, value_factory):
        async def sfn(*a, **kw):
            self.value = val = await value_factory(*a, **kw)
            return val

        return sfn

