# -*- coding: utf-8 -*-

from __future__ import unicode_literals, print_function

from tornado import gen
import simplejson as json

from components.api.handler import Handler
from components.common import CustomEncoder, send_post_request, Message
from bson import ObjectId

from tornado.ioloop import IOLoop
import time
import random


class LeafHandler(Handler):
    @gen.coroutine
    def post(self):
        """
        Создает новый лист.
        """
        data = json.loads(self.request.body)
        assert "name" and "type" and "address" in data

        leaf = yield self.application.async_db.leaves.update(
            {"name": data["name"]},
            {"$set": {"name": data["name"]}},
            upsert=True,
            new=True
        )
        if leaf["updatedExisting"]:
            self.note("Leaf with name {} already exists, pick another name")
            self.finish()
            raise gen.Return()

        leaf_id = leaf["upserted"]

        self.note("Looking up specie settings")
        try:
            query = {
                "_id": ObjectId(data["type"])
            }
        except:
            query = {
                "name": data["type"]
            }

        species = yield self.application.async_db.species.find_one(query)

        if not species:
            self.note("Unknown species specified, verify forest settings")
            self.finish()
            raise gen.Return()
        else:
            self.note("Using species {}[{}]".format(species["name"], species["_id"]))

        yield self.application.async_db.leaves.update(
            {"_id": leaf_id},
            {"$set": {
                "desc": "",
                "type": species["_id"],
                "active": True,
                "address": [data["address"]],
                "branch": None,
                "settings": {}
            }}
        )

        with Message(self, "Asking air to enable host..."):
            for air in self.application.druid.air:
                yield send_post_request(air, "air/hosts", {"host": data["address"]})

        if species.get("requires", []):
            self.note("Species {} requires following batteries: {}".format(
                species["name"],
                ", ".join(species["requires"]))
            )

            with Message(self, "Asking roots to prepare databases..."):
                roots = self.application.druid.roots[0]
                self.note("Using roots server at {}".format(roots["host"]))
                credentials = yield send_post_request(roots, "roots/db", {
                    "name": data["name"],
                    "db_type": species["requires"]
                })
                db_settings = credentials["data"]

                yield self.application.async_db.leaves.update(
                    {"_id": leaf_id},
                    {"$set": {
                        "batteries": db_settings
                    }}
                )

                response = "\n"
                for key, value in db_settings.items():
                    response += "Settings for {}\n".format(key)
                    response += "    User: {}\n".format(value["user"])
                    response += "    Pass: {}\n".format(value["pass"])
                    response += "    Name: {}\n".format(value["name"])
                self.note(response)
        else:
            db_settings = {}

        with Message(self, "Asking branch to host leaf"):
            branch = random.choice(self.application.druid.branch)
            self.note("Randomly chosen branch server at {}".format(branch["host"]))

            yield send_post_request(roots, "branch/leaves", {
                "_id": leaf_id
            })

        self.write("{}")
        self.flush()
        yield gen.Task(IOLoop.instance().add_timeout, time.time() + 5)
        self.finish(json.dumps({}, cls=CustomEncoder))
