from email.policy import default
from unittest.mock import MagicMock, Mock
import pytest
from inspect import Parameter




from laza.di.providers.functools import ParamResolver, _EMPTY
from laza.di.common import Inject
from laza.di.injectors import Injector


xfail = pytest.mark.xfail
parametrize = pytest.mark.parametrize





class ParamResolverTests:

    @parametrize(['value', 'default', 'annotation', 'has_value', 'has_default'], [
        (object(), object(), object, True, True),
        (Inject(str), Inject(list), object, False, False),
        (Inject(str, default='abc'), _EMPTY, str, False, False),
        ('123', str, Inject(str, default='abc'), True, True),
        (_EMPTY, _EMPTY, object, False, False),
    ])
    def test_basic(self, value, default, annotation, has_value, has_default):
        res = ParamResolver(value, default, annotation)
        assert isinstance(res, ParamResolver)
        assert res.value is value
        assert res.default is default
        assert res.annotation is annotation
        assert res.has_value == has_value
        assert res.has_default == has_default

    @parametrize(['resolver', 'exp'], [
        (ParamResolver(), _EMPTY),
        (ParamResolver(value='the value'), _EMPTY),
        (ParamResolver(default='default_value'), _EMPTY),
        (ParamResolver(value=list, default=dict), _EMPTY),
        (ParamResolver(value=Inject(object)), Inject(object)),
        (ParamResolver(default=Inject(object)), Inject(object)),
        (ParamResolver(annotation=object), object),
        (ParamResolver(annotation=Inject(object)), Inject(object)),
        (ParamResolver(value=Inject(object), default=Inject(list), annotation=str), Inject(object)),
        (ParamResolver(value=Inject(object), default=None, annotation=str), Inject(object)),
        (ParamResolver(value=None, default=Inject(list), annotation=str), Inject(list)),
        (ParamResolver(value=None, default=None, annotation=object), object),
        (ParamResolver(value=list, default=dict, annotation=object), object),
    ])
    def test_dependency(self, resolver: ParamResolver, exp):
        assert resolver.dependency == exp

    @parametrize(['resolver', 'exp'], [
        # (ParamResolver(), None),
        (ParamResolver(value='the value'), None),
        (ParamResolver(default='default_value'), None),
        (ParamResolver(value=list, default=dict), None),
        (ParamResolver(value=Inject(object)), Inject(object)),
        (ParamResolver(default=Inject(object)), Inject(object)),
        (ParamResolver(annotation=object), object),
        (ParamResolver(annotation=Inject(object)), Inject(object)),
        (ParamResolver(value=Inject(object), default=Inject(list), annotation=str), Inject(object)),
        (ParamResolver(value=Inject(object), default=None, annotation=str), Inject(object)),
        (ParamResolver(default=Inject(list), annotation=str), Inject(list)),
        (ParamResolver(value='wala', default=None, annotation=object), None),
        (ParamResolver(default=dict, annotation=object), object),
    ])
    def test_bind(self, resolver: ParamResolver, exp, injector: Injector):
        injector.is_provided = Mock(side_effect=lambda o: o == resolver.dependency)
        assert resolver.bind(injector) == exp

    @xfail(raises=TypeError)
    def test_bind_missing_dependency(self, injector: Injector):
        assert ParamResolver().bind(injector)

    @parametrize(['resolver', 'ctx', 'exp'], [
        (ParamResolver(), {}, (_EMPTY, _EMPTY, _EMPTY)),
        (ParamResolver(value='the value'), {}, ('the value', _EMPTY, _EMPTY)),
        (ParamResolver(default='default_value'), {}, (_EMPTY, _EMPTY, 'default_value')),
        (ParamResolver(value=list, default=dict), {}, (list, _EMPTY, _EMPTY)),
        (ParamResolver(value=Inject(object)), { Inject(object): Inject(object) }, (_EMPTY, Inject(object), _EMPTY)),
        (ParamResolver(default=Inject(object)), { Inject(object): Inject(object) }, (_EMPTY, Inject(object), _EMPTY)),
        (ParamResolver(value=Inject(object), default=Inject(str, default='default')), { Inject(object): Inject(object) }, (_EMPTY, Inject(object), _EMPTY)),
        (ParamResolver(annotation=object), { object: object }, (_EMPTY, object, _EMPTY)),
    ])
    def test_resolve(self, resolver: ParamResolver, ctx, exp):
        assert resolver.resolve(ctx) == exp

    @xfail(raises=LookupError)
    def test_resolve_missing_dependency(self):
        assert ParamResolver(Inject(object)).resolve({})

