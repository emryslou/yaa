import enum
import json
from typing import Mapping
from urllib.parse import unquote

from yast.datastructures import URL, Headers, QueryParams
from yast.types import Scope, Recevie, Send

class WebSocketState(enum.Enum):
    CONNECTING = 0
    CONNECTED = 1
    DISCONNECTED = 2

class WebSocketDisconnect(Exception):
    def __init__(self, code=1000):
        self.code = code

class WebSocketSession(Mapping):
    def __init__(self, scope: Scope, recevie: Recevie=None, send: Send=None):
        assert scope['type'] == 'websocket'
        self._scope = scope
        self._recevie = recevie
        self._send = send
        self.client_state = WebSocketState.CONNECTING
        self.application_state = WebSocketState.CONNECTING
    
    def __getitem__(self, key: str):
        return self._scope[key]
    
    def __iter__(self):
        return iter(self._scope)
    
    def __len__(self):
        return len(self._scope)
    
    @property
    def url(self) -> URL:
        if not hasattr(self, '_url'):
            scheme = self._scope['scheme']
            host, port = self._scope['server']
            path = self._scope.get('root_path', '') + self._scope['path']
            query_string = self._scope['query_string']

            if (scheme == 'ws' and port != 80) or (scheme == 'wss' and port != 443):
                url = '%s://%s:%s%s' % (scheme, host, port, path)
            else:
                url = '%s://%s%s' % (scheme, host, path)
            
            if query_string:
                url += '?' + unquote(query_string.decode())
            
            self._url = URL(url)
        
        return self._url
    
    @property
    def headers(self) -> Headers:
        if not hasattr(self, '_headers'):
            self._headers = Headers(self._scope['headers'])
        
        return self._headers
    

    @property
    def query_params(self) -> QueryParams:
        if not hasattr(self, '_query_parmas'):
            self._query_params = QueryParams(self._scope.get('query_string', '').decode())
        
        return self._query_params
    

    async def recevie(self):
        if self.client_state == WebSocketState.CONNECTING:
            message = await self._recevie()
            assert message['type'] == 'websocket.connect'
            self.client_state = WebSocketState.CONNECTED
            print('debug -- 014', message)
            return message
        elif self.client_state == WebSocketState.CONNECTED:
            message = await self._recevie()
            assert message['type'] in {'websocket.recevie', 'websocket.disconnect'}
            if message['type'] == 'websocket.disconnect':
                self.client_state = WebSocketState.DISCONNECTED
            return message
        else:
            raise RuntimeError(
                'Cannot call "recevie" once a disconnect message has been recevied'
            )

    async def send(self, message):
        if self.application_state == WebSocketState.CONNECTING:
            assert message['type'] in {'websocket.accept', 'websocket.close'}

            if message['type'] == 'websocket.close':
                self.application_state = WebSocketState.DISCONNECTED
            else:
                self.application_state = WebSocketState.CONNECTED
            
            await self._send(message)
        elif self.application_state == WebSocketState.CONNECTED:
            assert message['type'] in {'websocket.send', 'websocket.close'}

            if message['type'] == 'websocket.close':
                self.application_state = WebSocketState.DISCONNECTED
                
            await self._send(message)
        else:
            raise RuntimeError('Cannot call "send" once a close message has been sent.')
    
    async def accept(self, subprotocal=None):
        if self.client_state == WebSocketState.CONNECTING:
            await self.recevie()
        await self.send(
                {'type': 'websocket.accept', 'subprotocal': subprotocal}
            )
    
    def _raise_on_disconnect(self, message):
        if message is None:
            raise RuntimeError('Message is None')
        if message['type'] == 'websocket.disconnect':
            raise WebSocketDisconnect(message['code'])
    
    async def recevie_text(self):
        assert self.application_state == WebSocketState.CONNECTED

        message = await self.recevie()
        self._raise_on_disconnect(message)
        return message['text']
    
    async def recevie_bytes(self):
        assert self.application_state == WebSocketState.CONNECTED

        message = await self.recevie()
        self._raise_on_disconnect(message)
        return message['bytes']
    
    async def recevie_json(self):
        json_bytes = await self.recevie_bytes()
        return json.loads(json_bytes.decode('utf-8'))
    
    async def send_text(self, data: str):
        await self.send({'type': 'websocket.send', 'text': data})
    
    async def send_bytes(self, data: bytes):
        await self.send({'type': 'websocket.send', 'bytes': data})
    
    async def send_json(self, data):
        _j = json.dumps(data).encode('utf-8')
        await self.send({'type': 'websocket.send', 'bytes': _j})
    
    async def close(self, code=1000):
        await self.send({'type': 'websocket.close', 'code': code})
    
    