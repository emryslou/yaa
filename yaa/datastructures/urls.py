import typing
from collections import namedtuple
from collections.abc import Sequence
from shlex import shlex
from urllib.parse import SplitResult, parse_qsl, urlencode, urlsplit

from yaa.types import Scope

from .types import ImmutableMultiDict, MultiDict


class Address(typing.NamedTuple):
    host: typing.Optional[str]
    port: typing.Optional[int]


class CommaSeparatedStrings(Sequence):
    def __init__(self, value: typing.Union[str, typing.Sequence[str]]):
        if isinstance(value, str):
            splitter = shlex(value, posix=True)
            splitter.whitespace = ","
            splitter.whitespace_split = True
            self._items = [item.strip() for item in splitter]
        else:
            self._items = list(value)

    def __len__(self) -> int:
        return len(self._items)

    def __getitem__(self, index: typing.Union[int, slice]) -> typing.Any:
        return self._items[index]

    def __iter__(self) -> typing.Iterator[str]:
        return iter(self._items)

    def __repr__(self) -> str:
        list_repr = repr([item for item in self])
        return f"{self.__class__.__name__}({list_repr})"

    def __str__(self) -> str:
        return ", ".join(repr(item) for item in self)


class QueryParams(ImmutableMultiDict):
    def __init__(
        self,
        value: typing.Union[
            "ImmutableMultiDict",
            typing.Mapping,
            typing.List[typing.Tuple[typing.Any, typing.Any]],
        ] = None,
        scope: Scope = None,
        **kwargs: typing.Any,
    ) -> None:
        if kwargs:
            value = kwargs.pop("params", value)
            value = kwargs.pop("items", value)
            value = kwargs.pop("query_string", value)
            assert not kwargs, "Unknown parameter"

        if scope is not None:
            assert value is None, "Cannot set both `value` and `scope`"
            value = scope.get("query_string", b"").decode("latin-1")

        if isinstance(value, str) or isinstance(value, bytes):
            if isinstance(value, bytes):
                value = value.decode("latin-1")
            super().__init__(parse_qsl(value, keep_blank_values=True))
        else:
            super().__init__(value)

    def __str__(self) -> str:
        return urlencode(self._list)

    def __repr__(self) -> str:
        klass_name = self.__class__.__name__
        return f"{klass_name}(query_string={repr(str(self))})"


class Secret(object):
    def __init__(self, value: str) -> None:
        self._value = value

    def __repr__(self) -> str:
        klass_name = self.__class__.__name__
        return f"{klass_name}('********')"

    def __str__(self) -> str:
        return self._value


class URL(object):
    def __init__(
        self, url: str = "", scope: Scope = None, **components: typing.Any
    ) -> None:
        if scope is not None:
            assert not url, "Cannot set both `url` and `scope`"
            assert not components, "Cannot set both `**components` and `scope`"
            scheme = scope.get("scheme", "http")
            path = scope.get("root_path", "") + scope["path"]
            query_string = scope.get("query_string", b"")

            server = scope.get("server", None)
            host_header = None
            for _k, _v in scope.get("headers", []):
                if _k == b"host":
                    host_header = _v.decode("latin-1")
                    break
            if host_header is not None:
                url = f"{scheme}://{host_header}{path}"
            elif server is None:
                url = path
            else:
                host, port = server
                default_port = {"http": 80, "https": 443, "ws": 80, "wss": 443}[scheme]
                if port == default_port:
                    url = f"{scheme}://{host}{path}"
                else:
                    url = f"{scheme}://{host}:{port}{path}"

            if query_string:
                url += "?" + query_string.decode()
        elif components:
            assert not url, "Cannot set both `components` and `scope`"
            url = URL("").replace(**components).components.geturl()
        self._url = url

    @property
    def components(self) -> SplitResult:
        if not hasattr(self, "_components"):
            self._components = urlsplit(str(self._url))

        return self._components

    @property
    def scheme(self) -> str:
        return self.components.scheme

    @property
    def netloc(self) -> str:
        return self.components.netloc

    @property
    def path(self) -> str:
        return self.components.path

    @property
    def query(self) -> str:
        return self.components.query

    @property
    def fragment(self) -> str:
        return self.components.fragment

    @property
    def username(self) -> typing.Union[str, None]:
        return self.components.username

    @property
    def password(self) -> typing.Union[str, None]:
        return self.components.password

    @property
    def hostname(self) -> typing.Union[str, None]:
        return self.components.hostname

    @property
    def port(self) -> typing.Optional[int]:
        return self.components.port

    @property
    def is_secure(self) -> bool:
        return self.scheme in ("https", "wss")

    def replace(self, **kwargs: typing.Any) -> "URL":  # type: ignore
        if (
            "hostname" in kwargs
            or "port" in kwargs
            or "username" in kwargs
            or "password" in kwargs
        ):
            hostname = kwargs.pop("hostname", self.hostname)
            port = kwargs.pop("port", self.port)
            username = kwargs.pop("username", self.username)
            password = kwargs.pop("password", self.password)

            netloc = hostname

            if port is not None:
                netloc += f":{port}"
            if username is not None:
                userpass = username
                if password is not None:
                    userpass += f":{password}"
                netloc = f"{userpass}@{netloc}"

            kwargs["netloc"] = netloc
        components = self.components._replace(**kwargs)
        return self.__class__(components.geturl())

    def include_query_params(self, **kwargs: typing.Any) -> "URL":
        params = MultiDict(parse_qsl(self.query, keep_blank_values=True))
        params.update({str(key): str(value) for key, value in kwargs.items()})
        query = urlencode(params.multi_items())
        return self.replace(query=query)

    def replace_query_params(self, **kwargs: typing.Any) -> "URL":
        query = urlencode([(str(key), str(value)) for key, value in kwargs.items()])
        return self.replace(query=query)

    def remove_query_params(
        self, keys: typing.Union[str, typing.Sequence[str]]
    ) -> "URL":
        if isinstance(keys, str):
            keys = [keys]
        params = MultiDict(parse_qsl(self.query, keep_blank_values=True))
        for key in keys:
            params.pop(key, None)

        query = urlencode(params.multi_items())
        return self.replace(query=query)

    def __eq__(self, other: typing.Union[str, "URL"]) -> bool:
        return str(self) == str(other)

    def __str__(self) -> str:
        return str(self._url)

    def __repr__(self):
        url = str(self)
        if self.password:
            url = str(self.replace(password="********"))
        return f"{self.__class__.__name__}({repr(url)})"


class DatabaseURL(URL):
    def __init__(self, url: typing.Union[str, URL]) -> None:
        return super().__init__(str(url))

    @property
    def name(self) -> str:
        return self.path.lstrip("/")

    @property
    def database(self) -> str:
        return self.path.lstrip("/")

    def replace(self, **kwargs: typing.Any) -> "URL":
        if "name" in kwargs:
            kwargs["path"] = "/" + kwargs.pop("name")
        return super().replace(**kwargs)


class URLPath(str):
    def __new__(cls, path: str, protocol: str = "", host: str = "") -> str:
        assert protocol in ("http", "websocket", "")
        return str.__new__(cls, path)

    def __init__(self, path: str, protocol: str = "", host: str = "") -> None:
        self.protocol = protocol
        self.host = host

    def make_absolute_url(self, base_url: typing.Union[str, URL]) -> str:
        if isinstance(base_url, str):
            base_url = URL(base_url)

        if self.protocol:
            scheme = {
                "http": {True: "https", False: "http"},
                "websocket": {True: "wss", False: "ws"},
            }[self.protocol][base_url.is_secure]
        else:
            scheme = base_url.scheme

        if self.host:
            netloc = self.host
        else:
            netloc = base_url.netloc

        path = base_url.path.rstrip("/") + str(self)
        return str(URL(scheme=scheme, netloc=netloc, path=path))
