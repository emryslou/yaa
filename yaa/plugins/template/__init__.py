"""
name: template
description: 使用 jinja2模版 渲染 html
exposes:
    - plugin_init: 插件初始化
    - get_templates: 获取 Jinja2Template 初始化对象
"""
import functools
import typing

__name__ = "template"

from yaa.applications import Yaa

from .template import Jinja2Template

templates: Jinja2Template = None  # type: ignore[assignment]


def plugin_init(app: Yaa, config: dict = {}) -> None:
    """Template 插件初始化
    Args:
        app: Yaa 对象
        config: plugin 配置

    Returns:
        None

    Examples:
        plugin_init(..., config={})
    """
    if not config:
        return  # pragma: no cover
    global templates
    templates = Jinja2Template(**config)

    def get_template(app: Yaa, name: str) -> typing.Any:
        return templates.get_template(name)  # pragma: no cover

    app.get_template = functools.partial(get_template, app=app)  # type: ignore[attr-defined]


def get_templates() -> Jinja2Template:
    """获取 Jinja2Template 初始化对象
    Args:
        None

    Returns:
        Jinja2Template

    Raises:
        None

    Examples:
        # todo: none
    """

    global templates
    return templates
