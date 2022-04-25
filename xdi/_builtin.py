
from .containers import Container  
from .providers import AnnotatedProvider, UnionProvider, DepMarkerProvider, LookupMarkerProvider  




__builtin_container__ = Container(f'{__package__}.__builtin__')

_pro_union = UnionProvider()
_pro_dep = DepMarkerProvider()
_pro_annotated = AnnotatedProvider()
_pro_provided = LookupMarkerProvider()


__builtin_container__[_pro_dep.abstract] = _pro_dep
__builtin_container__[_pro_union.abstract] = _pro_union
__builtin_container__[_pro_provided.abstract] = _pro_provided
__builtin_container__[_pro_annotated.abstract] = _pro_annotated
