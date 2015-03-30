# coding=utf-8

from forest.components.branch.object import Branch
from forest.components.branch.handlers import LeavesHandler, LeafHandler, SpeciesListHandler, \
    SpeciesHandler, LoggerHandler, LoggerListHandler, LeafRPCHandler


branch_handlers = [
    # API листьев
    (r"/api/branch/leaf$", LeavesHandler),
    (r"/api/branch/leaf/([0-9a-fA-F]{24})$", LeafHandler),
    (r"/api/branch/leaf/([0-9a-fA-F]{24})/rpc$", LeafRPCHandler),
    # API видов
    (r"/api/branch/species$", SpeciesListHandler),
    (r"/api/branch/species/([0-9a-fA-F]{24})$", SpeciesHandler),
    # API логгеров
    (r"/api/branch/loggers$", LoggerListHandler),
    (r"/api/branch/loggers/([0-9a-fA-F]{*})$", LoggerHandler)
]

__all__ = ["Branch"]
