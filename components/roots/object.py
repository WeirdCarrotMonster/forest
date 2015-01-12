# -*- coding: utf-8 -*-
from __future__ import print_function, unicode_literals

from components.batteries import Mongo, MySQL


class Roots():
    def __init__(self, trunk, settings):
        self.settings = settings
        self.trunk = trunk

    def _stack_context_handle_exception(self, *args, **kwargs):
        print(args, kwargs)

    def create_db(self, name, db_type):
        if db_type == "mongo":
            return Mongo(self.settings["mongo"], self.trunk).prepare_leaf()
        elif db_type == "mysql":
            return MySQL(self.settings["mysql"], self.trunk).prepare_leaf()
