# -*- coding: utf-8 -*-
from __future__ import print_function, unicode_literals

from components.batteries import Mongo, MySQL
from components.common import log_message
from tornado.gen import Return, coroutine


class Roots():
    def __init__(self, trunk, settings):
        self.settings = settings
        self.trunk = trunk
        log_message("Started roots", component="Roots")

    def _stack_context_handle_exception(self, *args, **kwargs):
        print(args, kwargs)

    @coroutine
    def create_db(self, name, db_type):
        credentials = {}
        if "mongo" in db_type:
            credentials["mongo"] = yield Mongo(self.settings["mongo"], self.trunk).prepare_leaf(name)
        elif "mysql" in db_type:
            credentials["mysql"] = yield MySQL(self.settings["mysql"], self.trunk).prepare_leaf(name)
        raise Return(credentials)
