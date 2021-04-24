from pickle import GLOBAL
from djx.multisite.db.migrations.distribute import Distribute
import threading
from inspect import isgeneratorfunction
from contextlib import AbstractContextManager, contextmanager
from contextvars import ContextVar, copy_context

from collections import ChainMap
from collections.abc import  Generator, Mapping, MutableMapping



from typing import Any, Callable, ClassVar, Literal, Optional, Type, Union
from weakref import WeakValueDictionary
from flex.datastructures.enum import IntEnum
from flex.utils.decorators import export
from flex.utils import text


from .symbols import symbol
from .inspect import signature



BucketManager = Callable[..., AbstractContextManager[Mapping[Any, Any]]]


BucketManagerType = Union[BucketManager,Union[BucketManager, Generator[Mapping]]]]


__buckets: MutableMapping[str, BucketManagerType] = WeakValueDictionary()


def di_bucket_manager(manager: Optional[BucketManagerType] = None, /, *, 
                    name: Optional[str]=None, 
                    replace: Optional[BucketManager]=None) -> Callable[[], BucketManager]:
                    
    def decorator(mgr):
        name = name or text.slug(mgr.__name__).rstrip('_bucket')
        if isgeneratorfunction(mgr):
            mgr = contextmanager(mgr)

        if mgr is not(old := __buckets.setdefault(name, mgr)):
            if old is not replace:
                raise NameError(f'duplicate bucket {name=!r}')
            __buckets[name] = mgr

        return mgr

    return decorator(manager) if manager else decorator



def get_bucket_manager(name, default=...) -> BucketManager:
    try:
        return __buckets[name]
    except KeyError as e:
        if default is ...:
            raise LookupError(f'invalid bucket: {name=!r}') from e
        return default



__global_stack = []
@di_bucket_manager
def global_bucket():
    __global_stack.append(buc := {})
    try:
        yield ChainMap(*reversed(__global_stack))
    finally:
        __global_stack.remove(buc)
    


__thread_local = threading.local()
@di_bucket_manager
def thread_bucket():
    __thread_local.stack = getattr(__thread_local, 'stack', [])
    __thread_local.stack.append(buc := {})

    try:
        yield ChainMap(*reversed(__thread_local.stack))        
    finally:
        __thread_local.stack.remove(buc)



__context_stack = ContextVar('__context_stack')
@di_bucket_manager
def context_bucket():
    token = __context_stack.set(stack := list(__context_stack.get([])))
    stack.append({})
    try:
        yield ChainMap(*reversed(stack))
    finally:
        __context_stack.reset(token)
    



@export()
class Context(IntEnum):
    
    NONE = 0

    LOCAL = 10
    # WORKER = 20

    REQUEST = 30
    SESSION = 30

    SERVICE = 40
    CLUSTER = 50
    NETWORK = 50
    
    UNIVERSAL = 100









@export()
class Bucket(ChainMap, MutableMapping[symbol, Any]):
    """Bucket Object"""
    
    # __slots__ = ('scope', '_store', '_stack')

    scope: 'Scope'
    store: MutableMapping

    storefactory: Callable[..., MutableMapping] = dict

    def __init__(self, scope):
        self.scope = scope
        self.stack = []
        self._store = None

    @property
    def is_open(self):
        return bool(self.maps)

    @property
    def maps(self):
        return self.stack

    def setup(self):
        self.stack = []

    def teardown(self):
        self.stack = []

    def open(self):
        if not self.maps:
            self.setup()
        
        self._push_stack()

        return self

    def close(self, *exc):

        self._pop_stack()

        if not self.maps:
            self.teardown()

    __enter__ = open
    __exit__ = close
    
    def _push_stack(self):
        self.maps.insert(0, rv := {})
        return rv

    def _pop_stack(self):
        return self.maps.pop(0)

    def __call__(self):
        return self

    # def __contains__(self, o) -> bool:
    #     return o in self.store

    # def __len__(self) -> int:
    #     return len(self.store)

    # def __bool__(self) -> bool:
    #     return bool(self.store)

    # def __iter__(self):
    #     return iter(self.store)

    # def __getitem__(self, k):
    #     return self.store[k]

    # def __delitem__(self, k):
    #     del self.store[k]

    # def __setitem__(self, k, val):
    #     self.store[k] = val



class _ThreadStack(threading.local):

    def __init__(self, ) -> None:
        pass


@export()
class ThreadBucket(Bucket):
    

    def __init__(self, scope):
        super().__init__(scope)
        self._local = threading.local()
        self._local.stack = []

    @property
    def maps(self):
        return self._local.stack

    def setup(self):
        self._local.stack = []

    def teardown(self):
        self._local.stack = []

    @property
    def stack(self):
        return self._local.stack

    @property
    def store(self):
        return self._local.store

    def setup(self):
        self._local = threading.local()

    def teardown(self):
        self.store = None




@export()
class Scope:
    __slots__ = ('type')

    bucket_class: type[Bucket] = Bucket

    _types: ClassVar[Context] = Context

    def __call__(self, arg):
        return self.bucket_class(self)

    def push_bucket(self, arg) -> None:
        pass
    


