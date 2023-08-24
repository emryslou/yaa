from .datastructures import QueryParams, Headers, URL
import json


class Request:
    def __init__(self, scope, receive):
        self._scope = scope
        self._receive = receive

    @property
    def method(self):
        return self._scope["method"]

    @property
    def url(self):
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
    def headers(self):
        if not hasattr(self, "_headers"):
            self._headers = Headers(
                [
                    (key.decode(), value.decode())
                    for key, value in self._scope["headers"]
                ]
            )
        return self._headers

    @property
    def query_params(self):
        if not hasattr(self, "_query_params"):
            query_string = self._scope["query_string"].decode()
            self._query_params = QueryParams(query_string)
        return self._query_params

    async def body(self):
        if not hasattr(self, "_body"):
            body = b""
            while True:
                message = await self._receive()
                if message["type"] == "http.request":
                    body += message.get("body", b"")
                    if not message.get("more_body", False):
                        break
            self._body = body
        return self._body

    async def json(self):
        if not hasattr(self, "_json"):
            body = await self.body()
            self._json = json.loads(body)
        return self._json
