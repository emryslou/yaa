import typing

P = typing.ParamSpec("P")
T = typing.TypeVar("T")

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
SameSiteEnum = typing.Literal["lax", "strict", "none"]

Content = typing.Union[str, bytes]
SyncContentStream = typing.Iterator[Content]
AsyncContentStream = typing.AsyncIterator[Content]
ContentStream = typing.Union[SyncContentStream, AsyncContentStream]


StatelessLifespan = typing.Callable[[object], typing.AsyncContextManager[typing.Any]]
StateLifespan = typing.Callable[
    [typing.Any, typing.Dict[str, typing.Any]], typing.AsyncContextManager[typing.Any]
]
Lifespan = typing.Union[StatelessLifespan, StateLifespan]
