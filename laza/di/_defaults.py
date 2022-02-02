
from laza.common import typing as t
from .common import Depends, InjectedLookup
from . import providers as p

from .scopes import _ioc_local, _ioc_main

_ioc_local.provide(Depends, p.DependencyProvider())
_ioc_local.provide(t.Union, p.UnionProvider())
_ioc_local.provide(t.Annotated, p.AnnotationProvider())
_ioc_local.provide(InjectedLookup, p.LookupProvider())

