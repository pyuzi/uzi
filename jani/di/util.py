
import typing as t 



from jani.common.functools import export





from threading import Lock
from collections import Counter


__uid_map = Counter()
__uid_lock = Lock()

@export()
def unique_id(ns=None):
    global __uid_map, __uid_lock
    with __uid_lock:
        __uid_map[ns] += 1
        return __uid_map[ns]

