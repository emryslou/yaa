import typing

from yaa.requests import Request

TempleteContextProcessor = typing.Callable[[Request], typing.Dict[str, typing.Any]]
