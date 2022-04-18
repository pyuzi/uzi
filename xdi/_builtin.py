

import typing as t

from .containers import Container  
from .providers import AnnotatedProvider, UnionProvider, DepMarkerProvider, ProvidedMarkerProvider  




__builtin_container__ = Container(f'{__package__}.__builtin__')

_pro_union = UnionProvider()
_pro_annotated = AnnotatedProvider()
_pro_dep = DepMarkerProvider()
_pro_provided = ProvidedMarkerProvider()

__builtin_container__[_pro_union.abstract] = _pro_union
__builtin_container__[_pro_annotated.abstract] = _pro_annotated
__builtin_container__[_pro_dep.abstract] = _pro_dep
__builtin_container__[_pro_provided.abstract] = _pro_provided