# coding=utf-8
"""Модуль описывает методы API прокси-сервера и объект, работающий с ним."""

from forest.components.air.handlers import HostHandler
from forest.components.air.object import Air


air_handlers = [
    (r"/api/air/hosts", HostHandler),
]

__all__ = ["Air", "air_handlers"]
