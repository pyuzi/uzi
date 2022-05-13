from . import signals


from .containers import Container
from .providers import (
    AnnotationProvider,
    UnionProvider,
    DepMarkerProvider,
    LookupMarkerProvider,
)


@signals.on_container_create.connect
def _register_implicit_providers(sender: type[Container], container: Container):
    provs = (
        UnionProvider(),
        DepMarkerProvider(),
        AnnotationProvider(),
        LookupMarkerProvider(),
    )
    for prov in provs:
        container[prov.abstract] = prov
