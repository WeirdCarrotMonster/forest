# coding=utf-8

from forest.components.air.object import Air
from forest.components.air.handlers import HostHandler

air_handlers = [
    (r"/api/air/hosts", HostHandler),
]

__all__ = ["Air", "air_handlers"]
