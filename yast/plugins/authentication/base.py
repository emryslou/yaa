import asyncio
import functools
import inspect
import typing

from yast.exceptions import HttpException
from yast.requests import HttpConnection
from yast.responses import RedirectResponse, Response


def has_required_scope(conn: HttpConnection, scopes: typing.Sequence[str]) -> bool:
    try:
        for scope in scopes:
            if scope not in conn.auth.scopes:
                return False
    except BaseException as exc:  # pragma: nocover
        import sys  # pragma: nocover
        import traceback  # pragma: nocover

        traceback.print_tb(exc.__traceback__, file=sys.stdout)  # pragma: nocover
        raise exc  # pragma: nocover
    return True


def requires(
    scopes: typing.Union[str, typing.Sequence[str]],
    status_code: int = 403,
    redirect: str = None,
) -> typing.Callable:
    scope_list = [scopes] if isinstance(scopes, str) else scopes

    def decorator(func: typing.Callable) -> typing.Callable:
        _type = None
        is_async_func = asyncio.iscoroutinefunction(func)
        signature = inspect.signature(func)
        for idx, paramter in enumerate(signature.parameters.values()):
            if paramter.name in ("request", "websocket"):
                _type = paramter.name
                break
        else:
            raise Exception(
                f"No `request` or `websocket` argument on function `{func}`"
            )

        if _type == "request":

            @functools.wraps(func)
            async def wrapper(*args, **kwargs) -> Response:
                req = kwargs.get("request", args[idx])

                if not has_required_scope(req, scope_list):
                    if redirect is not None:
                        return RedirectResponse(url=req.url_for(redirect), status_code=303)
                    # endif
                    raise HttpException(status_code=status_code)
                # endif
                if is_async_func:
                    return await func(*args, **kwargs)
                else:
                    return func(*args, **kwargs)

            # end def wrapper

            return wrapper
        elif _type == "websocket":
            from yast.websockets import WebSocket

            @functools.wraps(func)
            async def ws_wrapper(*args, **kwargs) -> Response:
                ws_req = kwargs.get(_type, args[idx])

                assert isinstance(ws_req, WebSocket)

                if not has_required_scope(ws_req, scope_list):
                    await ws_req.close()
                else:
                    await func(*args, **kwargs)

            # end def ws_wrapper

            return ws_wrapper

    # end def decorator
    return decorator


class AuthenticationError(Exception):
    pass


class AuthenticationBackend(object):
    async def authenticate(self, conn: HttpConnection):
        raise NotImplementedError()  # pragma: nocover


class AuthCredentials(object):
    def __init__(self, scopes: typing.Sequence[str] = None) -> None:
        self.scopes = [] if scopes is None else scopes

    def __str__(self) -> str:
        return "%s(%s)" % (self.__class__.__name__, ",".join(self.scopes))

    def __repr__(self) -> str:
        return "%s(%s)" % (self.__class__.__name__, ",".join(self.scopes))


class BaseUser(object):
    @property
    def is_authenticated(self) -> bool:
        raise NotImplementedError()  # pragma: no cover

    @property
    def display_name(self) -> str:
        raise NotImplementedError()  # pragma: no cover

    @property
    def identity(self) -> str:
        raise NotImplementedError()  # pragma: no cover


class SimpleUser(BaseUser):
    def __init__(self, username: str) -> None:
        self.username = username

    @property
    def is_authenticated(self) -> bool:
        return True

    @property
    def display_name(self) -> str:
        return self.username

    @property
    def identity(self) -> str:
        raise ""  # pragma: nocover


class UnauthenticatedUser(BaseUser):
    @property
    def is_authenticated(self) -> bool:
        return False

    @property
    def display_name(self) -> str:
        return ""  # pragma: nocover

    @property
    def identity(self) -> str:
        raise ""  # pragma: nocover
