from typing import Iterator
from .datastructures import QueryParams, Headers, URL
from .types import Scope, Recevie

from collections.abc import Mapping
import json
import typing


class Request(Mapping):
    def __init__(self, scope: Scope, receive: Recevie = None):
        self._scope = scope
        self._receive = receive
        self._stream_consumed = False

    def __getitem__(self, __key: typing.Any) -> typing.Any:
        return self._scope[__key]
    
    def __iter__(self) -> Iterator:
        return iter(self._scope)
    
    def __len__(self) -> int:
        return len(self._scope)
    
    def set_recevie_channel(self, receive: Recevie):
        self._receive = receive

    @property
    def method(self) -> str:
        return self._scope["method"]

    @property
    def url(self) -> URL:
        if not hasattr(self, "_url"):
            scheme = self._scope["scheme"]
            host, port = self._scope["server"]
            path = self._scope["path"]
            query_string = self._scope["query_string"]

            if (scheme == "http" and port != 80) or (scheme == "https" and port != 443):
                url = "%s://%s:%s%s" % (scheme, host, port, path)
            else:
                url = "%s://%s%s" % (scheme, host, path)

            if query_string:
                url += "?" + query_string.decode()

            self._url = URL(url)
        return self._url

    @property
    def headers(self) -> Headers:
        if not hasattr(self, "_headers"):
            self._headers = Headers(
                [
                    (key.decode(), value.decode())
                    for key, value in self._scope["headers"]
                ]
            )
        return self._headers

    @property
    def query_params(self) -> QueryParams:
        if not hasattr(self, "_query_params"):
            query_string = self._scope["query_string"].decode()
            self._query_params = QueryParams(query_string)
        return self._query_params

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

    async def body(self):
        if not hasattr(self, "_body"):
            body = b""
            async for chunk in self.stream():
                body += chunk
            self._body = body
        return self._body

    async def json(self):
        if not hasattr(self, "_json"):
            body = await self.body()
            self._json = json.loads(body)
        return self._json
