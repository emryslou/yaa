"""
module: background
title: 后台任务
description: 后台任务，一般是在 http 响应任务后，执行后台任务
author: emryslou@gmail.com
examples: @(file):test_background.py
exposes:
    - BackgroundTask
    - BackgroundTasks
"""
import typing

from yaa._utils import is_async_callable
from yaa.concurrency import run_in_threadpool
from yaa.types import P


class BackgroundTask(object):
    """后台任务
    Attrs:
        func: 异步任务执行方法
        args: 异步任务参数
        kwargs: 异步任务参数
        is_async: 是否为 async 方法
    """

    def __init__(
        self, func: typing.Callable[P, typing.Any], *args: P.args, **kwargs: P.kwargs
    ) -> None:
        """初始化
        Args:
            func: 异步任务执行方法
            args: 异步任务参数
            kwargs: 异步任务参数

        Examples:
            def func():
                ...
            BackgroundTask(func=func)

            def func(arg1, arg2):
                ...
            BackgroundTask(func=func, arg1, arg2)
            BackgroundTask(func=func, arg1=..., arg2=...)
        """

        self.func = func
        self.args = args
        self.kwargs = kwargs
        self.is_async = is_async_callable(func)

    async def __call__(self) -> None:
        if self.is_async:
            await self.func(*self.args, **self.kwargs)
        else:
            await run_in_threadpool(self.func, *self.args, **self.kwargs)


class BackgroundTasks(BackgroundTask):
    """后台任务组
    Attrs:
        tasks: 后台任务列表
    """

    def __init__(self, tasks: typing.Sequence[BackgroundTask] = []) -> None:
        """初始化
        Args:
            tasks: 后台任务列表

        Examples:
            def func():
                ...
            bg1 = BackgroundTask(func=func)

            def func(arg1, arg2):
                ...
            bg2 = BackgroundTask(func=func, arg1, arg2)
            bg3 = BackgroundTask(func=func, arg1=..., arg2=...)

            BackgroundTasks([bg1, bg2, ...])
            BackgroundTasks()
        """

        self.tasks = list(tasks) if tasks else []

    def add_task(
        self, func: typing.Callable[P, typing.Any], *args: P.args, **kwargs: P.kwargs
    ) -> None:
        """添加任务
        Args:
            func: 异步任务执行方法
            args: 异步任务参数
            kwargs: 异步任务参数

        Examples:
            bgs = BackgroundTasks(...)

            def func():
                ...

            def func(arg1, arg2):
                ...

            bgs.add_task(func)
            bgs.add_task(func, arg1, arg2)
        """

        task = BackgroundTask(func, *args, **kwargs)
        self.tasks.append(task)

    async def __call__(self) -> None:
        for task in self.tasks:
            await task()
