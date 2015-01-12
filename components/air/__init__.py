#coding=utf-8

from components.air.object import Air
from components.air.handlers import HostHandler

air_handlers = [
    (r"/api/air/hosts", HostHandler),
]

__all__ = ["Air", "air_handlers"]
