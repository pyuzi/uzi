import typing as t
from dataclasses import dataclass


import pytest

from ...providers import (
    alias, provide, injectable
)
from ... import symbol, Depends, Scope
from ...symbols import _ordered_id


user_str = 'test-str'
user_symb = symbol('test-import')
noop_symb = symbol('noop-symbol')


class MainScope(Scope):

    class Config:
        name = Scope.MAIN
        
        
        

class LocalScope(Scope):

    class Config:
        name = 'local'

        

class AbcScope(Scope):

    class Config:
        name = 'abcd'
        depends = [
            'local'
        ]

        

@injectable(cache=True, scope=Scope.ANY)
class Foo:
    
    def __init__(self, name: Depends[str, 'foo.name'], user: Depends[str, user_str]) -> None:
        self.name = f'{name}  -> #{_ordered_id()}'
        self.user = user
    
    def __repr__(self):
        return f'Foo({self.name!r} u={self.user!r})'
    
    def __str__(self):
        return f'Foo({self.name!r} u={self.user!r})'


provide('foo.name', value='My Name Is Foo!!')

@injectable(scope=Scope.ANY, cache=True)
def user_func_injectable(user: Depends[str, user_str]):
    return f'user_func_injectable -> {user=!r} #{_ordered_id()}'


@injectable(cache=False, scope=Scope.ANY)
class Baz:
    pass



@injectable(cache=False)
class Bar:

    def __init__(self, foo: Foo, user: Depends[user_func_injectable], sym: Depends[str, user_symb], baz: Baz) -> None:
        self.foo = foo
        self.user = user
        self.sym = sym
        self.baz = baz
 
    def __repr__(self):
        return f'Bar(foo={self.foo!r}, user={self.user!r})'
    
    def __str__(self):
        return f'Bar(foo={self.foo!r}, user={self.user!r})'
    


def user_func_symb():
    return f'user_func_symb {user_symb} -> #{_ordered_id()}'
    

provide(user_symb, factory=user_func_symb, cache=True)


@injectable(abstract=user_str, cache=True)
def user_func_str():
    return f'user_func_str {user_str} -> #{_ordered_id()}'
    




