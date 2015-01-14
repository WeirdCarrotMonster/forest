#coding=utf-8

from components.druid.handlers import LeafHandler
from components.druid.object import Druid


druid_handlers = [
    (r"/api/druid/leaf", LeafHandler),
]

__all__ = ["Druid"]
