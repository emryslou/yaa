import typing
from urllib.parse import urlparse, parse_qsl, unquote, ParseResult

from yast.types import Scope, StrDict, StrPairs


class URL(object):
    def __init__(self, url: str = '', scope: Scope = None) -> None:
        if scope is not None:
            assert not url, 'Cannot set both "url" and "scope"'
            scheme = scope.get('scheme', 'http')
            path = scope.get('root_path', '') + scope['path']
            query_string = scope['query_string']
            
            server = scope.get('server', None)
            if server is None:
                url = path
            else:
                host, port = server
                default_port = {
                    'http': 80, 'https': 443,
                    'ws': 80, 'wss': 443
                }[scheme]
                if port == default_port:
                    url = '%s://%s%s' % (scheme, host, path)
                else:
                    url = '%s://%s:%s%s' % (scheme, host, port, path)
            
            if query_string:
                url += '?' + unquote(query_string.decode())
        
        self._url = url
    
    @property
    def components(self) -> ParseResult:
        if not hasattr(self, "_components"):
            self._components = urlparse(self._url)

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
    def params(self) -> str:
        return self.components.params

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

    def replace(self, **kwargs: typing.Any) -> "URL": # type: ignore

        if 'hostname' in kwargs or 'port' in kwargs:
            hostname = kwargs.pop('hostname', self.hostname)
            port = kwargs.pop('port', self.port)

            if port is None:
                kwargs['netloc'] = hostname
            else:
                kwargs['netloc'] = '%s:%d' % (hostname, port)

        components = self.components._replace(**kwargs)
        return URL(components.geturl())
    
    def __eq__(self, other: typing.Union[str, "URL"]) -> bool:
        return str(self) == str(other)
    
    def __str__(self):
        return self._url
    
    def __repr__(self):
        return '%s(%s)' % (self.__class__.__name__, repr(self._url))


class QueryParams(typing.Mapping[str, str]):
    def __init__(
        self, value: typing.Union[str, typing.Union[StrDict, StrPairs]] = None
    ) -> None:
        if value is None:
            value = []
        elif isinstance(value, str):
            value = parse_qsl(value)

        if hasattr(value, "items"):
            items = list(typing.cast(StrDict, value).items())
        else:
            items = list(typing.cast(StrPairs, value))
        self._dict = {k: v for k, v in reversed(items)}
        self._list = items

    def getlist(self, key: str) -> typing.List[str]:
        return [item_value for item_key, item_value in self._list if item_key == key]

    def keys(self):
        return [key for key, value in self._list]

    def values(self):
        return [value for key, value in self._list]

    def items(self):
        return list(self._list)

    def get(self, key, default=None):
        if key in self._dict:
            return self._dict[key]
        else:
            return default

    def __getitem__(self, key):
        return self._dict[key]

    def __contains__(self, key):
        return key in self._dict

    def __iter__(self):
        return iter(self._list)

    def __len__(self):
        return len(self._list)

    def __eq__(self, other):
        if not isinstance(other, QueryParams):
            other = QueryParams(other)
        return sorted(self._list) == sorted(other._list)

    def __repr__(self):
        return "QueryParams(%s)" % repr(self._list)


class Headers(typing.Mapping[str, str]):
    """ headers  """
    def __init__(self, value: typing.Union[StrDict, StrPairs] = None) -> None:
        if value is None:
            self._list = []
        else:
            assert isinstance(value, list)
            for h_k, h_v in value:
                assert isinstance(h_k, bytes)
                assert isinstance(h_v, bytes)
                assert h_k == h_k.lower()
            self._list = value

    def keys(self):
        return [key.decode('latin-1') for key, _ in self._list]

    def values(self):
        return [value.decode('latin-1') for _, value in self._list]

    def items(self):
        return [(k.decode('latin-1'), v.decode('latin-1')) for k, v in self._list]

    def get(self, key: str, default: str = None):
        try:
            return self[key]
        except KeyError:
            return default

    def getlist(self, key: str) -> typing.List[str]:
        h_k = key.lower().encode('latin-1')
        return [
            iv.decode('latin-1')
            for ik, iv in self._list
            if ik == h_k
        ]

    def mutablecopy(self):
        return MutableHeaders(self._list[:])

    def __getitem__(self, key: str):
        h_k = key.lower().encode('latin-1')
        for ik, iv in self._list:
            if h_k == ik:
                return iv.decode('latin-1')

        raise KeyError(key)

    def __contains__(self, key: str):
        return key.lower() in self.keys()

    def __iter__(self):
        return iter(self.items())

    def __len__(self):
        return len(self._list)

    def __eq__(self, other):
        if not isinstance(other, Headers):
            return False
        return sorted(self._list) == sorted(other._list)

    def __repr__(self):
        return "%s(%s)" % (self.__class__.__name__, repr(self.items()))


class MutableHeaders(Headers):
    def __setitem__(self, key: str, value: str):
        set_key = key.lower().encode('latin-1')
        set_value = value.encode('latin-1')

        pop_indexes = []
        for idx, (ik, _) in enumerate(self._list):
            if ik == set_key:
                pop_indexes.append(idx)
        
        """
        retain insertion order .
        """
        for idx in reversed(pop_indexes[1:]):
            del self._list[idx]

        if pop_indexes:
            self._list[pop_indexes[0]] = (set_key, set_value)
        else:
            self._list.append((set_key, set_value))

    def __delitem__(self, key: str):
        del_key = key.lower().encode('latin-1')
        pop_indexes = []
        for idx, (ik, _) in enumerate(self._list):
            if ik == del_key:
                pop_indexes.append(idx)
        
        for idx in reversed(pop_indexes):
            del self._list[idx]
    
    def setdefault(self, key: str, value: str):
        set_key = key.lower().encode('latin-1')
        set_value = value.encode('latin-1')

        for _, (itm_key, itm_val) in enumerate(self._list):
            if itm_key == set_key:
                return itm_val.decode('latin-1')
        
        self._list.append((set_key, set_value))
        return value
    
    def update(self, other: dict):
        for key, val in other.items():
            self[key] = val