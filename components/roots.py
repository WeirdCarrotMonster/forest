# -*- coding: utf-8 -*-
from __future__ import print_function, unicode_literals
import traceback

from tornado import gen
from tornado.gen import Return

from components.batteries import Mongo, MySQL


class Roots():
    def __init__(self, settings, trunk):
        self.settings = settings
        self.trunk = trunk

    def _stack_context_handle_exception(self, *args, **kwargs):
        print(args, kwargs)

    @gen.coroutine
    def periodic_event(self):
        cursor = self.trunk.async_db.leaves.find({
            "batteries": {"$exists": False},
            "locked": None
        })

        while (yield cursor.fetch_next):
            leaf = cursor.next_object()
            try:
                species = yield self.trunk.async_db.species.find_one({"_id": leaf.get("type")})

                locked_leaf = yield self.trunk.async_db.leaves.update(
                    {
                        "_id": leaf["_id"],
                        "locked": None
                    },
                    {
                        "$set": {"locked": self.trunk.id}
                    }
                )

                if not leaf or not species or not locked_leaf:
                    continue  # Обработка захвачена другим компонентом либо непонятная ебола
                    # TODO: обрабатывать получше

                requirements = species.get("requires", [])

                if "mongo" in requirements and "mongo" in self.settings:
                    mongo = Mongo(self.settings["mongo"], self.trunk)
                    mongo.prepare_leaf(leaf)

                if "mysql" in requirements and "mongo" in self.settings:
                    mysql = MySQL(self.settings["mysql"], self.trunk)
                    mysql.prepare_leaf(leaf)

                on_create = species.get("triggers", {}).get("on_create", [])
                if on_create:
                    yield self.trunk.async_db.leaves.update(
                        {"_id": leaf["_id"]},
                        {
                            "$set": {"locked": None},
                            "$push": {"tasks": {"type": "on_create", "cmd": on_create}}
                        }
                    )
                else:
                    yield self.trunk.async_db.leaves.update(
                        {"_id": leaf["_id"]},
                        {"$set": {"locked": None}}
                    )
            except:
                pass
