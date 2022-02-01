


from . import providers
from .containers import IocContainer





class Package:

    


    def __init__(self, ioc: IocContainer) -> None:
        self.ioc = ioc

    def providers(self):
        ioc = self.ioc




class SomePackage(Package):

    def providers(self):
        ioc = self.ioc
        ioc.type(Package, at='main', cache=True)

   
   