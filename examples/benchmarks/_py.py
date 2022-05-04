
from functools import cache


from _bench import ALL_DEPS, SINGLETON_DEPS



LABEL = 'py'


def _make_runner(cls, *deps, cached=False):
    # deps = [RUNNERS[d] for d in deps]
    return cache(cls._make_raw) if cached else fn


RUNNERS = {}
for cls, deps in ALL_DEPS.items():
    RUNNERS[cls] = cls._make_raw
    # RUNNERS[cls] = _make_runner(cls, *deps, cached=cls in SINGLETON_DEPS)



def get_runner(cls):
    return RUNNERS[cls]

