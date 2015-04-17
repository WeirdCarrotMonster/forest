# coding=utf-8
"""Модуль реализует набор хендлеров для обработки API-запросов и промежуточный класс-обработчик."""

from forest.components.druid.handlers import LeafHandler, LeafStatusHandler, \
    LeavesHandler, BranchHandler, BranchListHandler, LogHandler, WebsocketLogWatcher, \
    SpeciesListHandler, SpeciesHandler, TracebackHandler
from forest.components.druid.object import Druid


druid_handlers = [
    (r"/api/druid/leaf", LeavesHandler),
    (r"/api/druid/leaf\&address=([\w\d\.\-]*)", LeavesHandler),
    (r'/api/druid/leaf/([\w\d]+)', LeafHandler),
    (r'/api/druid/leaf/([\w\d]+)/status', LeafStatusHandler),

    (r'/api/druid/species', SpeciesListHandler),
    (r'/api/druid/species/([\w\d]+)', SpeciesHandler),

    (r'/api/druid/branch', BranchListHandler),
    (r'/api/druid/branch/?([\w\d]*)', BranchHandler),
    (r'/api/druid/logs', LogHandler),
    (r'/api/druid/logs/(\w*)', WebsocketLogWatcher),

    (r'/api/druid/traceback/(\w{8}\-\w{4}\-\w{4}\-\w{4}\-\w{12})', TracebackHandler)
]

__all__ = ["Druid"]
