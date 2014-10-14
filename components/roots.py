# -*- coding: utf-8 -*-
from __future__ import print_function, unicode_literals
from tornado import gen
from components.batteries import Mongo, MySQL


class Roots():
    def __init__(self, settings, trunk):
        self.settings = settings
        self.trunk = trunk

    def _stack_context_handle_exception(self, *args, **kwargs):
        print(args, kwargs)

    @gen.coroutine
    def periodic_event(self):
        cursor = self.trunk.async_db.leaves.find({"batteries": None})

        while (yield cursor.fetch_next):
            leaf = cursor.next_object()

            leaf_specie = yield self.trunk.async_db.species.find_one({"_id": leaf.get("type")})
            if not leaf_specie:
                continue

            requirements = leaf_specie.get("requires", [])

            if "mongo" in requirements and "mongo" in self.settings:
                mongo = Mongo(self.settings["mongo"], self.trunk)
                mongo.prepare_leaf(leaf)

            if "mysql" in requirements and "mongo" in self.settings:
                mysql = MySQL(self.settings["mysql"], self.trunk)
                mysql.prepare_leaf(leaf)
