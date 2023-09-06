import asyncio
import functools
import typing

import ujson as json

try:
    import graphene
    from graphql.error import GraphQLError, format_error as format_graphql_error
    from graphql.execution.executors.asyncio import AsyncioExecutor
except ImportError:
    graphene = None
    AsyncioExecutor = None
    format_graphql_error = None
    GraphQLError = None

import yast.status as web_status
from yast.requests import Request
from yast.responses import HTMLResponse, JSONResponse, PlainTextResponse, Response
from yast.types import ASGIInstance, Receive, Scope, Send


class GraphQLApp(object):
    def __init__(self, schema: "graphene.Schema", executor: typing.Any = None) -> None:
        assert graphene is not None, "python `graphene` package must be installed"
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
        if req.method == "GET":
            if "text/html" in req.headers.get("Accept", ""):
                return await self.handle_graphiql(req)

            data = req.query_params
        elif req.method == "POST":
            content_type = req.headers.get("Content-Type", "")
            if "application/json" in content_type:
                data = await req.json()
            elif "application/graphql" in content_type:
                body = await req.body()
                text = body.decode()
                data = {"query": text}
            elif "query" in req.query_params:
                data = req.query_params
            else:
                return PlainTextResponse(
                    "Unsupported Media Type",
                    status_code=web_status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
                )
        else:
            print("debug -- 01", req.method)
            return PlainTextResponse(
                "Method Not Allowed", status_code=web_status.HTTP_405_METHOD_NOT_ALLOWED
            )

        try:
            query = data["query"]
            variables = data.get("variables")
            operation_name = data.get("operationName")
        except KeyError:
            return PlainTextResponse(
                "No Graphql query found in the request",
                status_code=web_status.HTTP_400_BAD_REQUEST,
            )

        result = await self.execute(query, variables)
        err_data = (
            [format_graphql_error(err) for err in result.errors]
            if result.errors
            else None
        )
        res_data = {"data": result.data, "errors": err_data}

        status_code = (
            web_status.HTTP_400_BAD_REQUEST if result.errors else web_status.HTTP_200_OK
        )

        return JSONResponse(res_data, status_code=status_code)

    async def handle_graphiql(self, req: Request) -> Response:
        text = GRAPHIQL.replace("{{REQUEST_PATH}}", json.dumps(req.url.path))
        return HTMLResponse(text)

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


GRAPHIQL = """
<!--
 *  Copyright (c) Facebook, Inc.
 *  All rights reserved.
 *
 *  This source code is licensed under the license found in the
 *  LICENSE file in the root directory of this source tree.
-->
<!DOCTYPE html>
<html>
  <head>
    <style>
      body {
        height: 100%;
        margin: 0;
        width: 100%;
        overflow: hidden;
      }
      #graphiql {
        height: 100vh;
      }
    </style>
    <!--
      This GraphiQL example depends on Promise and fetch, which are available in
      modern browsers, but can be "polyfilled" for older browsers.
      GraphiQL itself depends on React DOM.
      If you do not want to rely on a CDN, you can host these files locally or
      include them directly in your favored resource bunder.
    -->
    <link href="//cdn.jsdelivr.net/npm/graphiql@0.12.0/graphiql.css" rel="stylesheet"/>
    <script src="//cdn.jsdelivr.net/npm/whatwg-fetch@2.0.3/fetch.min.js"></script>
    <script src="//cdn.jsdelivr.net/npm/react@16.2.0/umd/react.production.min.js"></script>
    <script src="//cdn.jsdelivr.net/npm/react-dom@16.2.0/umd/react-dom.production.min.js"></script>
    <script src="//cdn.jsdelivr.net/npm/graphiql@0.12.0/graphiql.min.js"></script>
  </head>
  <body>
    <div id="graphiql">Loading...</div>
    <script>
      /**
       * This GraphiQL example illustrates how to use some of GraphiQL's props
       * in order to enable reading and updating the URL parameters, making
       * link sharing of queries a little bit easier.
       *
       * This is only one example of this kind of feature, GraphiQL exposes
       * various React params to enable interesting integrations.
       */
      // Parse the search string to get url parameters.
      var search = window.location.search;
      var parameters = {};
      search.substr(1).split('&').forEach(function (entry) {
        var eq = entry.indexOf('=');
        if (eq >= 0) {
          parameters[decodeURIComponent(entry.slice(0, eq))] =
            decodeURIComponent(entry.slice(eq + 1));
        }
      });
      // if variables was provided, try to format it.
      if (parameters.variables) {
        try {
          parameters.variables =
            JSON.stringify(JSON.parse(parameters.variables), null, 2);
        } catch (e) {
          // Do nothing, we want to display the invalid JSON as a string, rather
          // than present an error.
        }
      }
      // When the query and variables string is edited, update the URL bar so
      // that it can be easily shared
      function onEditQuery(newQuery) {
        parameters.query = newQuery;
        updateURL();
      }
      function onEditVariables(newVariables) {
        parameters.variables = newVariables;
        updateURL();
      }
      function onEditOperationName(newOperationName) {
        parameters.operationName = newOperationName;
        updateURL();
      }
      function updateURL() {
        var newSearch = '?' + Object.keys(parameters).filter(function (key) {
          return Boolean(parameters[key]);
        }).map(function (key) {
          return encodeURIComponent(key) + '=' +
            encodeURIComponent(parameters[key]);
        }).join('&');
        history.replaceState(null, null, newSearch);
      }
      // Defines a GraphQL fetcher using the fetch API. You're not required to
      // use fetch, and could instead implement graphQLFetcher however you like,
      // as long as it returns a Promise or Observable.
      function graphQLFetcher(graphQLParams) {
        // This example expects a GraphQL server at the path /graphql.
        // Change this to point wherever you host your GraphQL server.
        return fetch({{REQUEST_PATH}}, {
          method: 'post',
          headers: {
            'Accept': 'application/json',
            'Content-Type': 'application/json',
          },
          body: JSON.stringify(graphQLParams),
          credentials: 'include',
        }).then(function (response) {
          return response.text();
        }).then(function (responseBody) {
          try {
            return JSON.parse(responseBody);
          } catch (error) {
            return responseBody;
          }
        });
      }
      // Render <GraphiQL /> into the body.
      // See the README in the top level of this module to learn more about
      // how you can customize GraphiQL by providing different values or
      // additional child elements.
      ReactDOM.render(
        React.createElement(GraphiQL, {
          fetcher: graphQLFetcher,
          query: parameters.query,
          variables: parameters.variables,
          operationName: parameters.operationName,
          onEditQuery: onEditQuery,
          onEditVariables: onEditVariables,
          onEditOperationName: onEditOperationName
        }),
        document.getElementById('graphiql')
      );
    </script>
  </body>
</html>
"""
