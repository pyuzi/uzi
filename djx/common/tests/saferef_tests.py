import pytest

from ..utils.saferef import safe_ref, strong_ref, weakref, ReferenceType



xfail = pytest.mark.xfail
parametrize = pytest.mark.parametrize





class RefTests:

    def test_basic(self):

        class Foo:
            pass
        
        t1 = Foo()
        r1 = safe_ref(t1)

        assert isinstance(r1, weakref)
        assert isinstance(r1, ReferenceType)
        assert t1 is r1()
        assert r1 is safe_ref(t1)
        assert r1 == strong_ref(t1)

        t2 = dict()
        r2 = safe_ref(t2)

        assert isinstance(r2, strong_ref)
        assert isinstance(r2, ReferenceType)
        assert t2 is r2()
        assert r2 == safe_ref(t2)
        assert r2 is safe_ref(t2)


        
    def test_callback(self):

        class Foo:
            _finalized = False
        
        t1 = Foo()
        def cb1(wr): 
            assert Foo._finalized is False
            Foo._finalized = True 
            print(f'FINALIZE FOO')

        r1 = safe_ref(t1, cb1)

        assert isinstance(r1, weakref)
        assert isinstance(r1, ReferenceType)
        assert t1 is r1()
        assert r1 == safe_ref(t1)
        assert r1.__callback__ is cb1
        

        del t1
        assert Foo._finalized

        class Dct:
            _finalized = False

        t2 = dict()

        def cb2(wr): 
            assert Dct._finalized is False
            print(f'FINALIZE dict')
            Dct._finalized = True 


        r2 = safe_ref(t2, cb2)

        assert isinstance(r2, ReferenceType)
        assert t2 is r2()
        assert r2 == safe_ref(t2)
        assert r2.__callback__ is cb2

        del r2
        assert Dct._finalized is True

        # assert 1

        