from pyinstrument import Profiler

import _xdi
import _py 
import _dependency_injector
import _antidot



import _bench
from _bench import Benchmark, ALL_DEPS


libs = {}
for mod in (_py, _antidot, _dependency_injector, _xdi):
    if mod.LABEL in libs:
        raise KeyError(f'{mod.__name__}.{mod.LABEL}')
    libs[mod.LABEL] = {
        d: mod.get_runner(d) for d in ALL_DEPS 
    }
    


N = int(5e4)

for dep in ALL_DEPS:
    runners = {
        k: dct[dep] for k, dct in libs.items()
    }
    
    bench = Benchmark(N).run(**runners)
    print(f"{dep.__name__}\n", bench.sorted(), "\n")


profiler = Profiler(interval=0.0001)

for dep in ALL_DEPS:
    runners = {
        k: dct[dep] for k, dct in libs.items()
    }

    for f in runners.values():
        with profiler:
            for _ in range(N):
                f()


profiler.open_in_browser()