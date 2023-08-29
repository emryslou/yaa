import pytest

from yast import TestClient
from yast.websockets import WebSocketSession, WebSocketDisconnect

class test_session_url():
    def app(scope):
        async def asgi(recevie, send):
            session = WebSocketSession(scope, recevie, send)
            await session.accept()
            await session.send_json({'url': session.url})
            await session.close()
        
        return asgi
    
    client = TestClient(app)
    with client.wsconnect('/aaa?b=ccc') as ss:
        data = ss.recevie_json()
        assert data == {'url': 'ws://testserver/aaa?b=ccc'}

class test_session_query_params():
    def app(scope):
        async def asgi(recevie, send):
            session = WebSocketSession(scope, recevie, send)
            await session.accept()
            await session.send_json({'params': dict(session.query_params)})
            await session.close()
        
        return asgi
    
    client = TestClient(app)
    with client.wsconnect('/aaa?b=ccc&d=22&ff=sss') as ss:
        data = ss.recevie_json()
        assert data == {'params': {'b': 'ccc', 'd': '22', 'ff': 'sss'}}
    
class test_session_headers():
    def app(scope):
        async def asgi(recevie, send):
            session = WebSocketSession(scope, recevie, send)
            await session.accept()
            await session.send_json({'headers': dict(session.headers)})
            await session.close()
        
        return asgi
    
    client = TestClient(app)
    with client.wsconnect('/aaa?b=ccc&d=22&ff=sss') as ss:
        data = ss.recevie_json()
        expected_headers = {
            'accept': '*/*',
            'accept-encoding': 'gzip, deflate',
            'connection': 'upgrade',
            'host': 'testserver',
            'user-agent': 'testclient',
            'sec-websocket-key': 'testserver==',
            'sec-websocket-version': '13',
        }
        assert data == {'headers': expected_headers}

class test_session_headers():
    def app(scope):
        async def asgi(recevie, send):
            session = WebSocketSession(scope, recevie, send)
            await session.accept()
            await session.send_json({'port': session.url.port})
            await session.close()
        
        return asgi
    
    client = TestClient(app)
    with client.wsconnect('ws://www.example.com:123/a?cc=cc') as ss:
        data = ss.recevie_json()
        
        assert data == {'port': 123}


def test_session_send_and_receive_text():
    def app(scope):
        async def asgi(receive, send):
            session = WebSocketSession(scope, receive, send)
            await session.accept()
            data = await session.recevie_text()
            await session.send_text("Message was: " + data)
            await session.close()
        return asgi
    client = TestClient(app)
    with client.wsconnect("/") as session:
        session.send_text("Hello, world!")
        data = session.recevie_text()
        assert data == "Message was: Hello, world!"