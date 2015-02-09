# coding=utf-8

from components.branch.object import Branch
from components.branch.handlers import LeavesHandler, LeafHandler, SpeciesListHandler, SpeciesHandler, LoggerHandler, LoggerListHandler


branch_handlers = [
    (r"/api/branch/leaf$", LeavesHandler),
    (r"/api/branch/leaf/([0-9a-fA-F]{24})$", LeafHandler),
    (r"/api/branch/species$", SpeciesListHandler),
    (r"/api/branch/species/([0-9a-fA-F]{24})$", SpeciesHandler),
    (r"/api/branch/loggers$", LoggerListHandler),
    (r"/api/branch/loggers/([0-9a-fA-F]{*})$", LoggerHandler)
]

__all__ = ["Branch"]
