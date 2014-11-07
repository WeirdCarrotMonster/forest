# coding=utf-8

from __future__ import unicode_literals, print_function
from datetime import datetime

from tornado import gen
import simplejson as json
from bson import ObjectId

from components.api.handler import Handler
from components.common import CustomEncoder
from components.decorators import login_required


class SpeciesHandler(Handler):
    @gen.coroutine
    @login_required
    def get(self):
        db = self.application.async_db
        cursor = db.species.find()

        self.write("[")

        beginning = True
        while (yield cursor.fetch_next):
            document = cursor.next_object()
            if beginning:
                beginning = False
            else:
                self.write(",")
            document["modified"] = document["modified"].generation_time
            self.write(json.dumps(document, cls=CustomEncoder))
        self.finish("]")


class SpecieHandler(Handler):
    @gen.coroutine
    @login_required
    def patch(self, _id):
        data = {"modified": ObjectId()}
        db = self.application.async_db
        species = yield db.species.find_and_modify(
            {"_id": ObjectId(_id)},
            {"$set": data},
            new=True
        )

        cursor = db.leaves.find({"type": ObjectId(_id)})
        on_update = species.get("triggers", {}).get("on_update", [])
        if on_update:
            while (yield cursor.fetch_next):
                leaf = cursor.next_object()

                yield db.task.insert({
                    "leaf": leaf["_id"],
                    "worker": None,
                    "type": "on_update",
                    "version": data["modified"],
                    "cmd": on_update
                })
        species["modified"] = species["modified"].generation_time
        self.finish(json.dumps(species, cls=CustomEncoder))