#coding=utf-8

from components.druid.handlers import LeafHandler, LeavesHandler
from components.druid.object import Druid


druid_handlers = [
    (r"/api/druid/leaf", LeavesHandler),
    (r'/api/druid/leaf/([\w\d]+)', LeafHandler)
]

__all__ = ["Druid"]
