#coding=utf-8

from components.druid.handlers import LeafHandler, LeavesHandler, SpeciesHandler, BranchHandler, LogHandler, LogWatcher
from components.druid.object import Druid


druid_handlers = [
    (r"/api/druid/leaf", LeavesHandler),
    (r'/api/druid/leaf/([\w\d]+)', LeafHandler),
    (r'/api/druid/species/([\w\d]+)', SpeciesHandler),
    (r'/api/druid/branch/([\w\d]+)', BranchHandler),
    (r'/api/druid/logs', LogHandler),
    (r'/api/druid/logs/(\w*)', LogWatcher),
]

__all__ = ["Druid"]
