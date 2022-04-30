
from . import signals


from .containers import Container  
from .providers import AnnotationProvider, UnionProvider, DepMarkerProvider, LookupMarkerProvider  





@signals.on_container_init.connect
def _register_implicit_providers(sender: type[Container], container: Container):
    _pro_union = UnionProvider()
    _pro_dep = DepMarkerProvider()
    _pro_annotated = AnnotationProvider()
    _pro_provided = LookupMarkerProvider()

    container[_pro_dep.abstract] = _pro_dep
    container[_pro_union.abstract] = _pro_union
    container[_pro_provided.abstract] = _pro_provided
    container[_pro_annotated.abstract] = _pro_annotated




