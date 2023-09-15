import asyncio
import functools
import typing

from yast.exceptions import HttpException
from yast.requests import Request
from yast.responses import RedirectResponse, Response


def has_required_scope(req: Request, scopes: typing.Sequence[str]) -> bool:
    try:
        for scope in scopes:
            if scope not in req.auth.scopes:
                return False
    except BaseException as exc:
        print("exception -- 02", exc)
        print("exception -- 02 - 02", scopes, req.auth.scopes)
        import sys
        import traceback

        traceback.print_tb(exc.__traceback__, file=sys.stdout)
        raise exc
    return True


def requires(
    scopes: typing.Union[str, typing.Sequence[str]],
    status_code: int = 403,
    redirect: str = None,
) -> typing.Callable:
    scope_list = [scopes] if isinstance(scopes, str) else scopes

    def decorator(func: typing.Callable) -> typing.Callable:
        if asyncio.iscoroutinefunction(func):

            @functools.wraps(func)
            async def wrapper(req: Request) -> Response:
                if not has_required_scope(req, scope_list):
                    if redirect is not None:
                        return RedirectResponse(url=req.url_for(redirect))
                    # endif
                    raise HttpException(status_code=status_code)
                # endif
                return await func(req)

            # end def func
            return wrapper
        else:

            @functools.wraps(func)
            def sync_wrapper(req: Request) -> Response:
                if not has_required_scope(req, scope_list):
                    if redirect is not None:
                        return RedirectResponse(url=req.url_for(redirect))
                    # endif
                    raise HttpException(status_code=status_code)
                return func(req)

            return sync_wrapper

    return decorator


class AuthenticationError(Exception):
    pass


class AuthenticationBackend(object):
    async def authenticate(self, req: Request):
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
        raise ""


class UnauthenticatedUser(BaseUser):
    @property
    def is_authenticated(self) -> bool:
        return False

    @property
    def display_name(self) -> str:
        return ""

    @property
    def identity(self) -> str:
        raise ""