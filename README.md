# 介绍
yet another startlette

# 版本 0.2.5
1. Opt: Add ImmutableMultiDict, Auth: Request -> HttpConnection, graphql: executor_class
2. database support: mysql
3. applications: auto scan plugins
4. applications: support subdomain router
5. formparser: upload file: content-type
6. base schema: add response; routing mount: add routes; code op
7. plugin: database: register custome databasebackend
8. requests: attr: database: removing next, attr: state: add
9. staticfile: support packages.static
10. wsgi: script read from scope[root_path]
11. config bool: 1 => True, 0 => False


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
pytest
pytest-cov
pytest-timeout
pytest-benchmark
flake8
mkdocs
mkdocs-material
isort
black
