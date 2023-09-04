import typing
from urllib.parse import urlparse, parse_qsl, urlencode, unquote, ParseResult

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
        self,
        params: typing.Mapping[str, str] = None,
        query_string: str = None,
        scope: Scope = None
    ) -> None:
        items = [] # type: typing.List[typing.Tuple[str, str]]
        if params is not None:
            assert query_string is None, 'Cannot set both `params` and `query_string`'
            assert scope is None, 'Cannot set both `params` and `scope`'
            items = list(params.items())
        elif query_string is not None:
            assert scope is None, 'Cannot set both `query_string` and `scope`'
            items = parse_qsl(query_string)
        elif scope is not None:
            items = parse_qsl(scope['query_string'].decode('latin-1'))
        
        self._dict = {k: v for k, v in reversed(items)}
        self._list = items

    def getlist(self, key: str) -> typing.List[str]:
        return [item_value for item_key, item_value in self._list if item_key == key]

    def keys(self) -> typing.List[str]:
        return [key for key, value in self._list]

    def values(self) -> typing.List[typing.Any]:
        return [value for key, value in self._list]

    def items(self) -> typing.List:
        return list(self._list)

    def get(self, key, default=None) -> typing.Any:
        if key in self._dict:
            return self._dict[key]
        else:
            return default

    def __getitem__(self, key) -> typing.Any:
        return self._dict[key]

    def __contains__(self, key) -> bool:
        return key in self._dict

    def __iter__(self) -> iter:
        return iter(self._list)

    def __len__(self):
        return len(self._list)

    def __eq__(self, other):
        if not isinstance(other, QueryParams):
            return False
        return sorted(self._list) == sorted(other._list)

    def __str__(self) -> str:
        return urlencode(self._list)

    def __repr__(self) -> str:
        return "%s(query_string=%s)" % (self.__class__.__name__, repr(str(self)))


class Headers(typing.Mapping[str, str]):
    """ headers  """
    def __init__(
            self,
            headers: typing.Mapping[str, str] = None,
            raw: typing.List[typing.Tuple[bytes, bytes]] = None,
            scope: Scope = None
        ) -> None:
        self._list = []
        if headers is not None:
            assert raw is None, 'Cannot set both `headers` and `raw`'
            assert scope is None, 'Cannot set both `headers` and `scope`'
            self._list = [
                (key.lower().encode('latin-1'), value.encode('latin-1'))
                for key, value in headers.items()
            ]
        elif raw is not None:
            assert scope is None, 'Cannot set both `raw` and `scope`'
            self._list = raw
        elif scope is not None:
            self._list = scope['headers']
    
    @property
    def raw(self) -> typing.List[typing.Tuple[bytes, bytes]]:
        return list(self._list)

    def keys(self):
        return [key.decode('latin-1') for key, _ in self._list]

    def values(self):
        return [value.decode('latin-1') for _, value in self._list]

    def items(self) -> typing.List[typing.Tuple[bytes, bytes]]:
        return [
                (k.decode('latin-1'), v.decode('latin-1')) 
                for k, v in self._list
            ]

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
        return MutableHeaders(raw=self._list[:])

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

    def __repr__(self) -> str:
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

    @property
    def raw(self) -> typing.List[typing.Tuple[bytes, bytes]]:
        return self._list
    
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
    
    def add_vary_header(self, vary):
        existing = self.get('vary')
        if existing is not None:
            vary = ', '.join([existing, vary])
        
        self['vary'] = vary