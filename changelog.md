# v0.2.5
1. Opt: Add ImmutableMultiDict, Auth: Request -> HttpConnection, graphql: executor_class
2. database support: mysql
3. applications: auto scan plugins
4. applications: support subdomain router
5. formparser: upload file: content-type
6. base schema: add response; routing mount: add routes; code op
7. plugin: database: register custome databasebackend

# v0.2.4
1. support template: default jinja2
2. staticfiles: method: head
3. route: support name
4. staticfiles: 304
5. request path: support path_params convert
6. makefile: python coverage
7. lifespan: as middleware
8. graphql: context
9. add DatabaseMiddleware: default postgresql
10. url: repr: hidden password; database backend constructor reconstruct
11. add authentication
12. plugins && add: executemany
13. plugins: add TemplatesResponse
14. formpaser: multi files


# v0.2.3
1. graphql: add graphiql
2. add route: suport graphql
3. lifespan: event_type support `shutdown`
4. middleware trustedhost: wildcards for domain
5. add middlewares: session , basehttp
6. support: clear session
7. support: schema auto generate
8. schema generate switch: default: on

# v0.2.2
1. middleware cors: support `allow_origin_regex`
2. support lifespan app.on_event: startup, cleanup
3. UJSONResponse & websocket: annotations
4. MultiPartParser
5. middleware gzip, wsgi
6. support graphql

# v0.2.1
1. 代码重构
2. testclient response reason
3. websocket endpoint
4. background task
5. middlewares: HttpsRedirect, CORS, TrustedHost

# v0.2.0
1. add object App & remove decorator AsgiApp
2. add view
3. exception handle
4. support cookie

# v0.1.5
1. fix: type expose

# v0.1.4
1. websocket
2. redirect response

# v0.1.3
1. debug middleware
2. [TODO]

# v0.1.2
1. async file & response
2. static files
3. relative_url
4. handle: http.disconnect

# v0.1.1
1. descorators can aysnc func
2. response stream


# v0.1.0
1. typing checking
2. support routing path / pathprefix
3. request read stream

# v0.0.1
1. 支持简单的 http 请求