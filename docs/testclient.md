# 说明
该模块可用于模拟请求

# 示例
```python
from yast import Yast, TestClient
from yast.responses import HTMLResponse


def app(scope):
    async def asgi(recv, send):
        await send({
            "type": "http.response.start",
            "status": 200,
            'headers': [
                (b'content-type', b'text/plain')
            ]
        })
        await send({
            "type": "http.response.body",
            "body": b'Hello'
        })
    return asgi


def test_app():
    client = TestClient(app)
    res = client.get('/')
    assert res.status_code == 200
    assert res.text == 'Hello'
```
# API
## TestClient:
| 参数 | [类型](/#typehint)                                       | 说明                                            |
| ---- | -------------------------------------------------------- | ----------------------------------------------- |
| app  | typing.Callable[[Receive, Send], typing.Awaitable[None]] | 请求处理入口，需返回 异步调用方法，用于处理请求 |
