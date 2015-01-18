# -*- coding: utf-8 -*-

from __future__ import unicode_literals, print_function

from tornado import gen
import simplejson as json

from components.api.handler import Handler
from components.common import send_post_request, send_request
from bson import ObjectId, json_util

import random


class LeavesHandler(Handler):

    @gen.coroutine
    def post(self):
        """
        Создает новый лист.
        """
        data = json.loads(self.request.body, object_hook=json_util.object_hook)
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
            query = {"_id": ObjectId(data["type"])}
        except:
            query = {"name": data["type"]}

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

        self.note("Asking air to enable host...")
        for air in self.application.druid.air:
            yield send_post_request(air, "air/hosts", {"host": data["address"]})

        if species.get("requires", []):
            self.note("Species {} requires following batteries: {}".format(
                species["name"],
                ", ".join(species["requires"]))
            )
            self.note("Asking roots to prepare databases...")

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

        self.note("Asking branch to host leaf")
        branch = random.choice(self.application.druid.branch)
        self.note("Randomly chosen branch server at {}".format(branch["host"]))

        yield self.application.async_db.leaves.update(
            {"_id": leaf_id},
            {"$set": {"branch": branch["name"]}}
        )

        leaf_config = yield self.application.async_db.leaves.find_one({"_id": leaf_id})
        leaf_config["fastrouters"] = ["{host}:{fastrouter}".format(**a) for a in self.application.druid.air]

        result = yield send_post_request(branch, "branch/leaves", leaf_config)
        if result["data"]["result"] == "started":
            self.note("Successfully started leaf")
        elif result["data"]["result"] == "queued":
            self.note("Leaf queued")
        else:
            self.note("Leaf start failed")
        self.finish()


class LeafHandler(Handler):

    @gen.coroutine
    def patch(self, leaf_name):
        # Обрабатываем только ключи active, address
        keys = ["active", "address"]
        data = json.loads(self.request.body, object_hook=json_util.object_hook)

        for key in data.keys():
            if key not in keys:
                del data[key]
        leaf_data = yield self.application.async_db.leaves.find_one({"name": leaf_name})
        if not leaf_data:
            self.note("Unknown leaf specified")
            self.finish()
            raise gen.Return()

        yield self.application.async_db.leaves.update(
            {"name": leaf_name},
            {"$set": data}
        )

        if data["active"] != leaf_data["active"]:
            leaf_data_new = yield self.application.async_db.leaves.find_one({"name": leaf_name})
            branch = next(x for x in self.application.druid.branch if x["name"] == leaf_data["branch"])

            if data["active"]:
                self.note("Starting leaf {}".format(leaf_name))
                leaf_data_new["fastrouters"] = ["{host}:{fastrouter}".format(**a) for a in self.application.druid.air]
                result = yield send_post_request(branch, "branch/leaves", leaf_data_new)
                if result["data"]["result"] == "started":
                    self.note("Successfully started leaf")
                elif result["data"]["result"] == "queued":
                    self.note("Leaf queued")
                else:
                    self.note("Leaf start failed")
            else:
                self.note("Stopping leaf {}".format(leaf_name))
                yield send_request(branch, "branch/leaf/{}".format(str(leaf_data["_id"])), "DELETE")
        self.finish()


class SpeciesHandler(Handler):

    @gen.coroutine
    def get(self, species_id):
        _id = ObjectId(species_id)
        species = yield self.application.async_db.species.find_one({"_id": _id})

        if not species:
            self.set_status(404)

        self.finish(json.dumps(species, default=json_util.default))


class BranchHandler(Handler):

    @gen.coroutine
    def put(self, branch_name):
        try:
            branch = next(x for x in self.application.druid.branch if x["name"] == branch_name)
        except:
            self.note("Unknown branch '{}'".format(branch_name))
            self.set_status(404)
            self.finish()
            raise gen.Return()

        self.note("Updating branch {} status...".format(branch["name"]))
        cursor = self.application.async_db.leaves.find({"branch": branch_name, "active": True})

        while (yield cursor.fetch_next):
            leaf = cursor.next_object()

            self.note("Starting leaf {}".format(leaf["name"]))
            leaf["fastrouters"] = ["{host}:{fastrouter}".format(**a) for a in self.application.druid.air]
            yield send_post_request(branch, "branch/leaves", leaf)

        self.finish(json.dumps({"result": "success"}))


class LogWatcher(Handler):

    @gen.coroutine
    def get(self, leaf_name):
        leaf_data = yield self.application.async_db.leaves.find_one({"name": leaf_name})
        if not leaf_data:
            self.set_status(404)
            self.finish()
            raise gen.Return()

        q = self.application.druid.get_listener(leaf_data["_id"])
        while not self.closed:
            data = yield q.get()
            self.note(json.dumps(data, default=json_util.default))


class LogHandler(Handler):

    @gen.coroutine
    def post(self):
        data = json.loads(self.request.body, object_hook=json_util.object_hook)
        yield self.application.druid.propagate_event(data)
        self.finish()
