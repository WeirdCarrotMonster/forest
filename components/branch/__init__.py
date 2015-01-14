#coding=utf-8

from components.branch.object import Branch
from components.branch.handlers import LeavesHandler


branch_handlers = [
    (r"/api/branch/leaves", LeavesHandler)
]

__all__ = ["Branch"]
