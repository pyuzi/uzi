import typing as t
from dataclasses import dataclass

from statistics import median, median_high, mean

import pytest

from ...providers import (
    alias, provide, injectable
)
from ... import symbol, Depends, Scope, InjectedClassVar, InjectedProperty, Injector
from ...symbols import _ordered_id


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
        


@injectable(cache=True, scope='any')
class Foo:
    
    def __init__(self, name: Depends[str, 'foo.name'], *, user: Depends[str, user_str],inj: Injector) -> None:
        self.name = f'{name} -> #{_ordered_id()}'
        self.user = user
        self.inj = inj
    
    def __repr__(self):
        return f'Foo({self.name!r} u={self.user!r} inj={self.inj})'
    
    def __str__(self):
        return f'Foo({self.name!r} u={self.user!r} inj={self.inj!r})'


provide('foo.name', value='My Name Is Foo!!')



class Follow:
    pass



alias(Follow, Foo, cache=False)

@injectable(scope=Scope.ANY, cache=True)
def user_func_injectable(user: Depends[str, user_str], d2: Follow):
    return f'user_func_injectable -> {user=!r} #{_ordered_id()}'


@injectable(cache=False)
class Baz:

    def __init__(self):
        self.abc = f'Baz -> #{_ordered_id()}'
    




alias('bar', user_func_injectable, cache=False)


@injectable(cache=False, scope=Scope.ANY)
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
        self.pk = _ordered_id()
 
    def __repr__(self):
        return f'{self}'
    
    def __str__(self):
        return f'Bar#{self.pk}(foo={self.foo!r}, user={self.user!r})'
    


def user_func_symb():
    return f'user_func_symb {user_symb} -> #{_ordered_id()}'
    

provide(user_symb, factory=user_func_symb, cache=False)


@injectable(abstract=user_str, cache=False)
def user_func_str():
    return f'user_func_str {user_str} -> #{_ordered_id()}'
    




def ops_per_sec(n, *vals):
    val = mean(vals)
    return n * (1/val), val, sum(vals, 0)



