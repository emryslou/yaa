import json
import typing
import http.cookies
from collections.abc import Mapping
from urllib.parse import unquote
from typing import Iterator

from yast.datastructures import QueryParams, Headers, URL
from yast.types import Scope, Receive



class ClientDisconnect(Exception):
    pass

class Request(Mapping):
    def __init__(
            self, scope: Scope,
            receive: Receive = None
        ):
        self._scope = scope
        self._receive = receive
        self._stream_consumed = False
        self._cookies = None

    def __getitem__(self, __key: typing.Any) -> typing.Any:
        return self._scope[__key]
    
    def __iter__(self) -> Iterator:
        return iter(self._scope)
    
    def __len__(self) -> int:
        return len(self._scope)
    
    def set_receive_channel(self, receive: Receive) -> None:
        self._receive = receive

    @property
    def method(self) -> str:
        return self._scope["method"]

    @property
    def url(self) -> URL:
        if not hasattr(self, "_url"):
            self._url = URL(scope=self._scope)
        return self._url
    

    @property
    def relative_url(self) -> URL:
        if not hasattr(self, '_relative_url'):
            url = self._scope['path']
            query_str = self._scope['query_string']

            if query_str:
                url += '?' + unquote(query_str.decode())
            
            self._relative_url = url
        
        return self._relative_url

    @property
    def headers(self) -> Headers:
        if not hasattr(self, "_headers"):
            self._headers = Headers(self._scope["headers"])
        return self._headers

    @property
    def query_params(self) -> QueryParams:
        if not hasattr(self, "_query_params"):
            query_string = self._scope["query_string"].decode()
            self._query_params = QueryParams(query_string)
        return self._query_params

    @property
    def cookie(self) -> typing.Dict[str, str]:
        if hasattr(self, '_cookies'):
            cookies = {}
            cookie_headers = self.headers.get('cookie')
            if cookie_headers:
                cookie = http.cookies.SimpleCookie()
                cookie.load(cookie_headers)
                for k, morse in cookie.items():
                    cookies[k] = morse.value
            self._cookies = cookies
        return self._cookies

    async def stream(self):
        if hasattr(self, "_body"):
            yield self._body
            return
        
        if self._stream_consumed:
            raise RuntimeError('Stream consumed')
        
        self._stream_consumed = True
        while True:
            message = await self._receive()
            if message['type'] == 'http.request':
                yield message.get('body', b'')
                if not message.get('more_body', False):
                    break
            elif message['type'] == 'http.disconnect':
                raise ClientDisconnect()

    async def body(self) -> bytes:
        if not hasattr(self, "_body"):
            body = b""
            async for chunk in self.stream():
                body += chunk
            self._body = body
        return self._body

    async def json(self) -> typing.Any:
        if not hasattr(self, "_json"):
            body = await self.body()
            self._json = json.loads(body)
        return self._json
