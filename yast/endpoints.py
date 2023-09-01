import asyncio
import typing
import ujson as json

from yast.exceptions import HttpException
from yast.requests import Request
from yast.responses import Response, PlainTextResponse
from yast.types import Message, Receive, Scope, Send
from yast.websockets import WebSocket


class HttpEndPoint(object):
    def __init__(self, scope: Scope) -> None:
        self.scope = scope
    
    async def __call__(self, receive: Receive, send: Send) -> None:
        req = Request(self.scope, receive) 
        res = await self.dispatch(req, **self.scope.get('kwargs', {}))

        await res(receive, send)
    
    async def dispatch(self, req: Request, **kwargs: typing.Any) -> Response:
        handler_name = 'get' if req.method == 'HEAD' else req.method.lower()
        handler = getattr(self, handler_name, self.method_not_allowed)

        if asyncio.iscoroutinefunction(handler):
            res = await handler(req, **kwargs)
        else:
            res = handler(req, **kwargs)
        return res
    
    async def method_not_allowed(self, req: Request, **kwargs: typing.Any):
        if 'app' in self.scope:
            raise HttpException(status_code=405)
        return PlainTextResponse('Method Not Allowed', 405)

class WebSocketEndpoint(object):
    encoding = None # 'text', 'bytes', 'json'
    ws: WebSocket = None

    def __init__(self, scope: Scope) -> None:
        self.scope = scope
    
    async def __call__(self, receive: Receive, send: Send) -> None:
        self.ws = WebSocket(self.scope, receive, send)
        kwargs = self.scope.get('kwargs', {})
        await self.on_connect(**kwargs)

        close_code = None
        try:
            while True:
                message = await self.ws.receive()
                if message['type'] == 'websocket.receive':
                    data = await self.decode(message)
                    await self.on_receive(data)
                elif message['type'] == 'websocket.disconnect':
                    close_code = message.get('code', 1000)
                    return
        finally:
            await self.on_disconnect(close_code)
    
    async def send(self, data, send_type: str = 'bytes'):
        fn = getattr(self.ws, 'send_'+ send_type)
        await fn(data)

    async def decode(self, message: Message):
        if self.encoding is not None:
            decode_fn_name = '_decode_' + self.encoding.lower()
            if not hasattr(self, decode_fn_name):
                decode_fn_name = '_decode_unknown'
        else:
            decode_fn_name = '_decode_none'

        decode_fn = getattr(self, decode_fn_name)
        return await decode_fn(message)
    
    async def _decode_text(self, message: Message):
        if 'text' not in message:
            await self.ws.close(1003) 
            raise RuntimeError('Expected text websocket messages, but got others')
        return message['text']

    async def _decode_bytes(self, message: Message):
        if 'bytes' not in message: 
            await self.ws.close(1003)
            print('debug -- 004', message)
            raise RuntimeError('Expected bytes websocket messages, but got others')
        return message['bytes']

    async def _decode_json(self, message: Message):
        if 'bytes' not in message:
            await self.ws.close(1003) 
            raise RuntimeError('Expected json websocket messages, but got others')
        
        return json.loads(message['bytes'].decode('utf-8'))
    
    async def _decode_unknown(self, message: Message):
        return await self._decode_text(message) 
    
    async def _decode_none(self, message: Message):
        return await self._decode_text(message)
    
    async def on_connect(self, **kwargs: typing.Any) -> None:
        """Override to handle an incoming websocket connection"""
        await self.ws.accept()
    
    async def on_receive(self, data):
        """Override to handle an incoming websocket message"""
        pass

    async def on_disconnect(self, code: int):
        """Override to handle a disconnecting websocket"""
        pass
