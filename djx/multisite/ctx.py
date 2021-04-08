
from contextvars import ContextVar, copy_context, Token
from contextlib import contextmanager
from typing import Any, ClassVar, List, Optional, Tuple, TypeVar, Union

from django.db.models.base import Model

from flex.utils.proxy import Proxy
from flex.utils.decorators import export



_SitePK = TypeVar('_SitePK', int, str, None)


_site_pk_ctx_var: ContextVar[Tuple[_SitePK, ...]] = ContextVar('_site_pk_ctx_var', default=())

__all__ = [
    'current_site',
]


@export()
def get_current_site(default: Union[_SitePK, Model] = None) -> Optional[Model]:
    from .models import impl
    return impl.Site._default_manager.get_current()


def get_all_current_site_pks() -> Tuple[_SitePK, ...]:
    return _site_pk_ctx_var.get(())




current_site: Proxy[Optional[Model]] = Proxy(get_current_site)



@export()
@contextmanager
def use_site(site: Union[Model, _SitePK], *extra: Union[Model, _SitePK]):
    sites = tuple(dict(((pk, pk) for v in ((site,) + extra)  if (pk := _get_site_pk(v)))))
    token = _site_pk_ctx_var.set(sites)

    print(f'+++ switch sites {token.old_value} -->', get_all_current_site_pks())

    try:
        yield get_current_site()
        print(f' - start using site -->', get_all_current_site_pks(), '-->', get_current_site())
    finally:
        print(f' - end using site   -->', s := get_all_current_site_pks())
        _site_pk_ctx_var.reset(token)

    print(f'--- reset sites {s} ---> {token.old_value}')





def _get_site_pk(val):
    return val.pk if isinstance(val, Model) else val


