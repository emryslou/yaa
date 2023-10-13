import typing

StrPairs = typing.Sequence[typing.Tuple[str, str]]
StrDict = typing.Mapping[str, str]

Scope = typing.Mapping[str, typing.Any]
Message = typing.Mapping[str, typing.Any]

Receive = typing.Callable[[], typing.Awaitable[Message]]
Send = typing.Callable[[Message], typing.Awaitable[None]]

ASGIInstance = typing.Callable[[Receive, Send], typing.Awaitable[None]]
ASGIApp = typing.Callable[[Scope], ASGIInstance]
ASGI3App = typing.Callable[[Scope, Receive, Send], typing.Awaitable[None]]

HeaderRaw = typing.List[typing.Tuple[bytes, bytes]]
HeaderRawOptional = typing.Optional[HeaderRaw]

P = typing.ParamSpec("P")
T = typing.TypeVar("T")
