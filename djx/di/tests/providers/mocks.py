import typing as t
from dataclasses import dataclass

from statistics import median, median_high, mean

import pytest

from ...inspect import ordered_id

from djx.common.saferef import StrongRef as symbol

from djx.di import ioc, Depends, Scope, InjectedProperty, Injector, abc


abc.Injectable.register(symbol)


user_str = 'test-str'
user_symb = symbol('test-import')
noop_symb = symbol('noop-symbol')


class Level2Scope(Scope):

    class Config:
        name = 'level_2'
        depends = [
            'request'
        ]
        
class Level3Scope(Scope):

    class Config:
        name = 'level_3'
        depends = [
            'level_2'
        ]
        

class Level4Scope(Scope):

    class Config:
        name = 'level_4'
        depends = [
            'level_3'
        ]
        

class Level5Scope(Scope):

    class Config:
        name = 'level_5'
        depends = [
            'level_4'
        ]
        


class CliScope(Scope):

    class Config:
        name = 'cli'
        depends = [
            'console'
        ]
        

class _TestScope(Scope):

    class Config:
        name = 'test'
        depends = [
            # 'cli',
            'level_5'
        ]
        


@ioc.type(cache=True, at='main')
class Foo:
    
    def __init__(self, name: Depends[str, 'foo.name'], *, user: Depends[str, user_str], inj: Injector) -> None:
        self.name = f'{name} -> #{ordered_id()}'
        self.user = user
        self.inj = inj
    
    def __repr__(self):
        return f'Foo({self.name!r}, inj={self.inj})'
    
    def __str__(self):
        return f'Foo({self.name!r}' #' u={self.user!r} inj={self.inj!r})'


ioc.value('foo.name', 'My Name Is Foo!!')



class Follow:
    pass



ioc.alias(Follow, Foo, cache=False)


@ioc.function(at=Scope.ANY, cache=True)
def user_func_injectable(user: Depends[str, user_str], d2: Follow):
    return f'user_func_injectable -> {user=!r} #{ordered_id()}'


@ioc.injectable(at=Scope.ANY, cache=True)
def user_func_injectable(user: Depends[str, user_str], d2: Follow):
    return f'user_func_injectable -> {user=!r} #{ordered_id()}'


@ioc.injectable(at='any', cache=False)
class Baz:

    def __init__(self):
        self.abc = f'Baz -> #{ordered_id()}'
    




ioc.alias('bar', user_func_injectable, cache=False)


@ioc.injectable(cache=False, at=Scope.MAIN)
class Bar:

    infoo = InjectedProperty(Foo)

    def __init__(self, foo: Foo, 
                    flw: Follow, 
                    sbar: Depends[str, 'bar'], 
                    user: Depends[str, user_func_injectable], *, 
                    sym: Depends[str, user_symb], baz: Baz, kw2=...) -> None:
        self.foo = foo
        self.flw = flw
        self.sbar = sbar
        self.user = user
        self.sym = sym
        self.baz = baz
        self.kw2 = kw2
        self.pk = ordered_id()
 
    def __repr__(self):
        nl = "\n"
        tb = "\t"
        sep = f",{nl}{tb}"
        return f'{self.__class__.__name__}({nl}{tb}{sep.join(f"{k}={v!r}" for k, v in self.__dict__.items())}{nl})'
    
    def __str__(self):
        return f'Bar#{self.pk}(foo={self.foo!r}: user={self.user!r})'
    

@ioc.function(user_symb)
def user_func_symb():
    return f'user_func_symb {user_symb} -> #{ordered_id()}'
    

@ioc.injectable(user_str, cache=False)
@ioc.injectable()
def user_func_str(p=None):
    return f'user_func_str {user_str} -> {p=!r} -> #{ordered_id()}'
    


