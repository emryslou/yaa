import asyncio
import functools
import typing

try:
    import graphene
    from graphql.execution.executors.asyncio import AsyncioExecutor
    from graphql.error import format_error as format_graphql_error
    from graphql.error import GraphQLError
except ImportError:
    graphene = None
    AsyncioExecutor = None
    format_graphql_error = None
    GraphQLError = None

from yast.requests import Request
from yast.responses import Response, PlainTextResponse, JSONResponse
import yast.status as web_status
from yast.types import ASGIInstance, Scope, Receive, Send

class GraphQLApp(object):
    def __init__(
            self,
            schema: "graphene.Schema",
            executor: typing.Any = None
        ) -> None:
        assert graphene is not None, 'python `graphene` package must be installed'
        self.schema = schema
        self.executor = executor
        self.is_async = isinstance(executor, AsyncioExecutor)
    
    def __call__(self, scope: Scope) -> ASGIInstance:
        return functools.partial(self.asgi, scope=scope)
    
    async def asgi(self, receive: Receive, send: Send, scope: Scope) -> None:
        req = Request(scope=scope, receive=receive)
        res = await self.handler(req)
        await res(receive, send)
    
    async def handler(self, req: Request) -> Response:
        if req.method == 'GET':
            data = req.query_params
        elif req.method == 'POST':
            content_type = req.headers.get('Content-Type', '')
            if 'application/json' in content_type:
                data = await req.json()
            elif 'application/graphql' in content_type:
                body = await req.body()
                text = body.decode()
                data = {'query': text}
            elif 'query' in req.query_params:
                data = req.query_params
            else:
                return PlainTextResponse('Unsupported Media Type',status_code=web_status.HTTP_415_UNSUPPORTED_MEDIA_TYPE)
        else:
            return PlainTextResponse('Method Not Allowed', status_code=web_status.HTTP_405_METHOD_NOT_ALLOWED)
        
        try:
            query = data['query']
            variables = data.get('variables')
            operation_name = data.get('operationName')
        except KeyError:
            return PlainTextResponse(
                    'No Graphql query found in the request',
                    status_code=web_status.HTTP_400_BAD_REQUEST
                )
        
        result = await self.execute(query, variables)
        err_data = (
            [format_graphql_error(err) for err in result.errors]
            if result.errors else None
        )
        res_data = {"data": result.data, 'errors': err_data}

        status_code = (
            web_status.HTTP_400_BAD_REQUEST
            if result.errors else web_status.HTTP_200_OK
        )

        return JSONResponse(res_data, status_code=status_code)

    async def execute(self, query, variable=None, operation_name=None):
        if self.is_async:
            return await self.schema.execute(
                query,
                variable=variable,
                operation_name=operation_name,
                executor=self.executor,
                return_promise=True,
            )
        else:
            func = functools.partial(
                self.schema.execute, variable=variable, operation_name=operation_name
            )
            loop = asyncio.get_event_loop()
            return await loop.run_in_executor(None, func, query)