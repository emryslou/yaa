import typing

StrPairs = typing.Sequence[typing.Tuple[str, str]]
StrDict = typing.Mapping[str, str]

Scope = typing.Mapping[str, typing.Any]
Message = typing.Mapping[str, typing.Any]

Receive = typing.Callable[[], typing.Awaitable[Message]]
Send = typing.Callable[[Message], typing.Awaitable[None]]

ASGIInstance = typing.Callable[[Receive, Send], typing.Awaitable[None]]
ASGIApp = typing.Callable[[Scope], ASGIInstance]

P = typing.ParamSpec("P")
T = typing.TypeVar("T")
