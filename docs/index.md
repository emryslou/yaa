# 说明

# Python 环境
Python 3.10+

# 安装
```shell
# todo next ...
```

# 示例
```python
from yast import Yast
from yast.responses import JSONResponse

app = Yast()

@app.route('/')
async def index(request):
    return JSONResponse({'demo': 'this is a demo'})

if __name__ == '__main__':
    uvicorn.run(app, host='0.0.0.0', port=8000)
```

# 依赖包

# [类型定义](#typehint)
```python
import typing

StrPairs = typing.Sequence[typing.Tuple[str, str]]
StrDict = typing.Mapping[str, str]

Scope = typing.Mapping[str, typing.Any]
Message = typing.Mapping[str, typing.Any]

Receive = typing.Callable[[], typing.Awaitable[Message]]
Send = typing.Callable[[Message], typing.Awaitable[None]]

ASGIInstance = typing.Callable[[Receive, Send], typing.Awaitable[None]]
ASGIApp = typing.Callable[[Scope], ASGIInstance]
```