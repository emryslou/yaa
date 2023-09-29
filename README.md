# 介绍
yet another startlette

# 版本 0.3.0
1. asgi: 2.0 -> 3.0
2. StaticFiles: dir => dir/index.html, not found(html=True): 404.html
3. Adding a percent sign to redirect with quoted params
4. app run: trace-id
5. server-push , app state
6. [known issue] see skip test case


# 功能说明
1. 内置测试客户端 `TestClient`
2. 支持 `CORS`, `GZip`, `Static Files`, `Streaming Responses`
3. 支持 Session 和 Cookie
4. 支持事件: startup、shutdown
5. 支持文档生成

# 依赖包
requests
aiofiles
ujson
python-multipart
itsdangerous
graphql-core < 3
graphene
pyyaml
sqlalchemy >= 1.0, < 2.0.0
asyncpg
psycopg2-binary
aiomysql
pymysql
cryptography
mypy
pytest
pytest-asyncio
pytest-cov
pytest-timeout
pytest-benchmark
flake8
mkdocs
mkdocs-material
isort
black
