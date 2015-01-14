#coding=utf-8

from components.roots.object import Roots
from components.roots.handlers import DatabaseHandler


roots_handlers = [
    (r"/api/roots/db", DatabaseHandler),
]

__all__ = ["Roots", "roots_handlers"]
