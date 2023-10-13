"""
module: Middlewares
title: 授权插件相关中间件
description:
    授权插件相关中间件， 主要包含如下:
    - AuthenticationMiddleware: 授权中间件
author: emryslou@gmail.com
examples: test_responses.py
"""
import typing

from yaa.middlewares.core import Middleware
from yaa.requests import HttpConnection
from yaa.responses import PlainTextResponse, Response
from yaa.types import ASGI3App, Receive, Scope, Send

from .base import (
    AuthCredentials,
    AuthenticationBackend,
    AuthenticationError,
    AuthenticationOnErrorCall,
    UnauthenticatedUser,
)


class AuthenticationMiddleware(Middleware):
    def __init__(
        self,
        app: ASGI3App,
        backend: AuthenticationBackend,
        debug: bool = False,
        on_error: typing.Optional[AuthenticationOnErrorCall] = None,
    ) -> None:
        """AuthenticationMiddleware
        param: app: 处理接受后回调 asgi 应用
        param: backend: 授权后端处理对象, 需继承自 AuthenticationBackend
        param: debug: 是否开启调试
        param: on_error: 错误处理函数
        """
        super().__init__(app)
        self.debug = debug
        self.backend = backend
        self.on_error: AuthenticationOnErrorCall = (
            on_error if on_error is not None else self.default_on_error
        )

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] in ("http", "websocket"):
            await self.asgi(scope=scope, receive=receive, send=send)  # type: ignore
        else:
            await self.app(scope, receive=receive, send=send)  # type: ignore

    async def asgi(self, receive: Receive, send: Send, scope: Scope) -> None:
        conn = HttpConnection(scope=scope)
        try:
            auth_result = await self.backend.authenticate(conn)
        except AuthenticationError as exc:
            if scope["type"] == "websocket":
                from yaa.websockets import WebSocketClose

                ws_close = WebSocketClose()
                await ws_close(scope, receive, send)
            else:
                res = self.on_error(conn, exc)
                await res(scope, receive, send)
            return
        except BaseException as exc:
            if self.debug:
                raise exc
            else:
                res = self.default_on_error(
                    conn, AuthenticationError(f"server error: {exc}")
                )
                await res(scope, receive, send)
                return
        if auth_result is None:
            auth_result = AuthCredentials(), UnauthenticatedUser()

        scope["auth"], scope["user"] = auth_result  # type: ignore

        await self.app(scope, receive, send)  # type: ignore

    @staticmethod
    def default_on_error(conn: HttpConnection, exc: AuthenticationError) -> Response:
        return PlainTextResponse(str(exc), status_code=400)
