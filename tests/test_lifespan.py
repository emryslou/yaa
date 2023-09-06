import pytest

from yast.lifespan import LifeSpanHandler, LifeSpanContext, EventType


def test_lifespan_sync():
    handler = LifeSpanHandler()
    su_done = False
    cu_done = False

    @handler.on_event("startup")
    def fn_su():
        nonlocal su_done
        su_done = True

    @handler.on_event("shutdown")
    def fn_cu():
        nonlocal cu_done
        cu_done = True

    assert not su_done, "LifeSpan Su Should Not Done 0"
    assert not cu_done, "LifeSpan Cu Should Not Done 0"
    with LifeSpanContext(handler):
        assert su_done, "LifeSpan Su Should Be Done 1"
        assert not cu_done, "LifeSpan Cu Should Not Done 1"

    assert su_done, "LifeSpan Su Should Be Done 2"
    assert cu_done, "LifeSpan Su Should Be Done 2"


def test_lifespan_async():
    handler = LifeSpanHandler()
    su_done = False
    cu_done = False

    @handler.on_event("startup")
    async def fn_su():
        nonlocal su_done
        su_done = True

    @handler.on_event("shutdown")
    async def fn_cu():
        nonlocal cu_done
        cu_done = True

    assert not su_done, "LifeSpan Su Should Not Done 0"
    assert not cu_done, "LifeSpan Cu Should Not Done 0"
    with LifeSpanContext(handler):
        assert su_done, "LifeSpan Su Should Be Done 1"
        assert not cu_done, "LifeSpan Cu Should Not Done 1"

    assert su_done, "LifeSpan Su Should Be Done 2"
    assert cu_done, "LifeSpan Su Should Be Done 2"


def test_lifespan_app():
    from yast.applications import Yast

    su_done = False
    cu_done = False

    handler = Yast()

    @handler.on_event("startup")
    async def fn_su():
        nonlocal su_done
        su_done = True

    @handler.on_event("shutdown")
    async def fn_cu():
        nonlocal cu_done
        cu_done = True

    assert not su_done, "LifeSpan Su Should Not Done 0"
    assert not cu_done, "LifeSpan Cu Should Not Done 0"
    with LifeSpanContext(handler):
        assert su_done, "LifeSpan Su Should Be Done 1"
        assert not cu_done, "LifeSpan Cu Should Not Done 1"

    assert su_done, "LifeSpan Su Should Be Done 2"
    assert cu_done, "LifeSpan Su Should Be Done 2"
