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
        while True:
            task = yield self.trunk.async_db.task.find_and_modify(
                {"worker": None, "type": "create_db"},
                {"$set": {"worker": self.trunk.settings["id"], "status": "processing"}}
            )

            if not task:
                break

            try:
                leaf = yield self.trunk.async_db.leaves.find_one(task["leaf"])
                species = yield self.trunk.async_db.species.find_one({"_id": leaf.get("type")})

                if not leaf or not species:
                    raise Exception()

                requirements = species.get("requires", [])

                if "mongo" in requirements and "mongo" in self.settings:
                    mongo = Mongo(self.settings["mongo"], self.trunk)
                    mongo.prepare_leaf(leaf)

                if "mysql" in requirements and "mongo" in self.settings:
                    mysql = MySQL(self.settings["mysql"], self.trunk)
                    mysql.prepare_leaf(leaf)

                result = []
                error = []

                on_create = species.get("triggers", {}).get("on_create", [])
                if on_create:
                    yield self.trunk.async_db.task.insert({
                        "leaf": leaf["_id"],
                        "worker": None,
                        "type": "on_create",
                        "version": species["modified"],
                        "cmd": on_create
                    })

                yield self.trunk.async_db.task.find_and_modify(
                    {"_id": task["_id"]},
                    {"$set": {"status": "finished", "result": result, "error": error}}
                )
            except:
                yield self.trunk.async_db.task.find_and_modify(
                    {"_id": task["_id"]},
                    {"$set": {"status": "failed", "error": traceback.fomat_exc()}}
                )
