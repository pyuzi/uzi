import typing as t


import pytest



from laza.di import (
    ioc, Depends, Scope, InjectedProperty, Injector,
    Injectable, 
)

from laza.di.util import unique_id



token_abc = Injectable('abc')
token_xyz = Injectable('xyz')


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
        


I_FooName = Injectable('foo.name')

@ioc.type(shared=True, at='main')
class Foo:
    
    def __init__(self, name: Depends(str, on=I_FooName), *, user: Depends(str, on=token_abc), inj: Injector) -> None:
        self.name = f'{name} -> #{unique_id(Foo)}'
        self.user = user
        self.inj = inj
    
    def __repr__(self):
        return f'Foo({self.name!r}, inj={self.inj})'
    
    def __str__(self):
        return f'Foo({self.name!r}' #' u={self.user!r} inj={self.inj!r})'


ioc.value(I_FooName, 'My Name Is Foo!!')


@ioc.alias(use=Foo, shared=False)
class Follow:
    pass






@ioc.function(at='any', shared=True)
def user_func_injectable(user: Depends(str, on=token_abc), d2: Follow):
    return f'user_func_injectable -> {user=!r} #{unique_id()}'


@ioc.injectable(at='any', shared=True)
def user_func_injectable(user: Depends(str, on=token_abc), d2: Follow):
    return f'user_func_injectable -> {user=!r} #{unique_id()}'




I_Bar = Injectable('I_Bar')

ioc.alias(I_Bar, user_func_injectable, shared=False)


@ioc.injectable(shared=False, at='any')
class Bar:

    infoo = InjectedProperty(Foo, scope='level_4')

    def __init__(self, foo: Foo, 
                    flw: Follow, 
                    sbar: Depends(str, on=I_Bar), 
                    user: Depends(str, on=user_func_injectable), *, 
                    sym: Depends(str, on=token_xyz), baz: 'Baz', kw2=...) -> None:
        self.foo = foo
        self.flw = flw
        self.sbar = sbar
        self.user = user
        self.sym = sym
        self.baz = baz
        self.kw2 = kw2
        self.pk = f'Bar:{unique_id(Bar)}'
 
    def __repr__(self):
        nl = "\n"
        tb = "\t"
        sep = f",{nl}{tb}"
        return f'{self.__class__.__name__}({nl}{tb}{sep.join(f"{k}={v!r}" for k, v in self.__dict__.items())}{nl})'
    
    def __str__(self):
        return f'Bar#{self.pk}(foo={self.foo!r}: user={self.user!r})'
    

@ioc.function(token_xyz)
def user_func_symb():
    return f'user_func_symb {token_xyz} -> #{unique_id(token_xyz)}'
    

@ioc.injectable(token_abc, shared=False)
@ioc.injectable()
def user_func_str(p=None):
    return f'user_func_str {token_abc} -> {p=!r} -> #{unique_id(token_abc)}'
    

@ioc.injectable(at='any', shared=False)
class Baz:

    def __init__(self):
        self.abc = f'Baz -> #{unique_id()}'
    


