# -*- coding: utf-8 -*-

from __future__ import unicode_literals, print_function

from tornado import gen
import simplejson as json

from components.api.handler import Handler
from components.api.decorators import token_auth
from components.common import send_post_request, send_request
from bson import ObjectId, json_util
import random


class LeavesHandler(Handler):

    @gen.coroutine
    @token_auth
    def get(self):
        cursor = self.application.async_db.leaves.find()
        self.write("[")
        first = True
        while (yield cursor.fetch_next):
            if not first:
                self.write(",")
            else:
                first = False

            leaf = cursor.next_object()
            self.write(json.dumps(leaf["name"]))
        self.finish("]")

    @gen.coroutine
    @token_auth
    def post(self):
        """
        Создает новый лист.
        """
        try:
            data = json.loads(self.request.body, object_hook=json_util.object_hook)
        except:
            self.set_status(400)
            self.finish(json.dumps({
                "result": "error",
                "message": "Malformed json"
            }))
            raise gen.Return()
        assert "name" and "type" and "address" in data
        leaf_name = data["name"]
        leaf_type = data["type"]
        leaf_address = data["address"]
        leaf_settings = data.get("settings", {})
        leaf_desc = data.get("description", "")

        leaf_address_check = yield self.application.async_db.leaves.find_one({"address": leaf_address})

        if leaf_address_check:
            self.note("Leaf with address {} already exists, pick another name".format(leaf_address))
            self.set_status(400)
            self.finish(json.dumps({
                "result": "error",
                "message": "Duplicate address"
            }))
            raise gen.Return()

        leaf = yield self.application.async_db.leaves.update(
            {"name": leaf_name},
            {"$set": {"name": leaf_name}},
            upsert=True,
            new=True
        )

        if leaf["updatedExisting"]:
            self.note("Leaf with name {} already exists, pick another name".format(leaf_name))
            self.set_status(400)
            self.finish(json.dumps({
                "result": "error",
                "message": "Duplicate name"
            }))
            raise gen.Return()

        leaf_id = leaf["upserted"]

        self.note("Looking up species settings")
        try:
            query = {"_id": ObjectId(leaf_type)}
        except:
            query = {"name": leaf_type}

        species = yield self.application.async_db.species.find_one(query)

        if not species:
            self.note("Unknown species specified, verify forest settings")
            self.set_status(400)
            self.finish(json.dumps({
                "result": "error",
                "message": "Unknown species"
            }))
            raise gen.Return()
        else:
            self.note("Using species {}[{}]".format(species["name"], species["_id"]))

        yield self.application.async_db.leaves.update(
            {"_id": leaf_id},
            {"$set": {
                "desc": leaf_desc,
                "type": species["_id"],
                "active": True,
                "address": [leaf_address],
                "branch": None,
                "settings": leaf_settings
            }}
        )

        self.note("Asking air to enable host...")
        for air in self.application.druid.air:
            yield send_post_request(air, "air/hosts", {"host": leaf_address})

        if species.get("requires", []):
            self.note("Species {} requires following batteries: {}".format(
                species["name"],
                ", ".join(species["requires"]))
            )
            self.note("Asking roots to prepare databases...")

            roots = self.application.druid.roots[0]
            self.note("Using roots server at {}".format(roots["host"]))
            credentials = yield send_post_request(roots, "roots/db", {
                "name": leaf_name,
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

        # ==============
        # Проверяем наличие искомого типа на ветви
        # ==============

        response, code = yield send_request(
            branch,
            "branch/species/{}".format(species["_id"]),
            "GET"
        )

        if code == 404:
            response, code = yield send_request(
                branch,
                "branch/species".format(species["_id"]),
                "POST",
                species
            )

        result = yield send_post_request(branch, "branch/leaf", leaf_config)
        if result["data"]["result"] == "started":
            self.note("Successfully started leaf")
        elif result["data"]["result"] == "queued":
            self.note("Leaf queued")
        else:
            self.note("Leaf start failed")
        self.finish(json.dumps({"result": "success", "message": "OK"}))


class LeafHandler(Handler):

    @gen.coroutine
    @token_auth
    def get(self, leaf_name):
        leaf_data = yield self.application.async_db.leaves.find_one({"name": leaf_name})

        if not leaf_data:
            self.set_status(404)
            self.finish("")

        self.finish(json.dumps(leaf_data, default=json_util.default))

    @gen.coroutine
    @token_auth
    def patch(self, leaf_name):
        # Обрабатываем только ключи active, address
        apply_changes = self.get_argument("apply", default="TRUE").upper() == "TRUE"

        keys = ["active", "address"]
        data = json.loads(self.request.body, object_hook=json_util.object_hook)

        for key in data.keys():
            if key not in keys:
                del data[key]

        leaf_data = yield self.application.async_db.leaves.find_one({"name": leaf_name})
        if not leaf_data:
            self.note("Unknown leaf specified")
            self.set_status(404)
            self.finish(json.dumps({"result": "success", "message": "Unknown leaf"}))
            raise gen.Return()

        yield self.application.async_db.leaves.update(
            {"name": leaf_name},
            {"$set": data}
        )

        leaf_data = yield self.application.async_db.leaves.find_one({"name": leaf_name})

        if apply_changes:
            if leaf_data["active"]:
                branch = next(x for x in self.application.druid.branch if x["name"] == leaf_data["branch"])

                self.note("Starting leaf {}".format(leaf_name))
                leaf_data["fastrouters"] = [
                    "{host}:{fastrouter}".format(**a) for a in self.application.druid.air
                ]
                result = yield send_post_request(branch, "branch/leaf", leaf_data)

                if result["data"]["result"] == "started":
                    self.note("Successfully started leaf")
                elif result["data"]["result"] == "queued":
                    self.note("Leaf queued")
                else:
                    self.note("Leaf start failed")
            else:
                branch = next(x for x in self.application.druid.branch if x["name"] == leaf_data["branch"])
                self.note("Stopping leaf {}".format(leaf_name))
                yield send_request(branch, "branch/leaf/{}".format(str(leaf_data["_id"])), "DELETE")
        self.finish(json.dumps({"result": "success", "message": "OK"}))


class LeafStatusHandler(Handler):

    @gen.coroutine
    @token_auth
    def get(self, leaf_name):
        leaf_data = yield self.application.async_db.leaves.find_one({"name": leaf_name})

        if not leaf_data:
            self.set_status(404)
            self.finish("")

        branch = next(x for x in self.application.druid.branch if x["name"] == leaf_data["branch"])
        leaf_status, code = yield send_request(branch, "branch/leaf/{}".format(str(leaf_data["_id"])), "GET")

        self.finish(json.dumps(leaf_status, default=json_util.default))


class SpeciesHandler(Handler):

    @gen.coroutine
    @token_auth
    def get(self, species_id):
        _id = ObjectId(species_id)
        species = yield self.application.async_db.species.find_one({"_id": _id})

        if not species:
            self.set_status(404)

        self.finish(json.dumps(species, default=json_util.default))


class BranchHandler(Handler):

    @gen.coroutine
    @token_auth
    def get(self, branch_name=None):
        if branch_name:
            self.finish("{}")
        else:
            self.finish(json.dumps([x["name"] for x in self.application.druid.branch]))

    @gen.coroutine
    @token_auth
    def put(self, branch_name=None):
        assert branch_name
        try:
            branch = next(x for x in self.application.druid.branch if x["name"] == branch_name)
        except:
            self.note("Unknown branch '{}'".format(branch_name))
            self.set_status(404)
            self.finish()
            raise gen.Return()

        self.note("Updating branch {} status...".format(branch["name"]))
        cursor = self.application.async_db.leaves.find({"branch": branch_name, "active": True})

        verified_species = set()

        while (yield cursor.fetch_next):
            leaf = cursor.next_object()

            self.note("Starting leaf {}".format(leaf["name"]))
            leaf["fastrouters"] = ["{host}:{fastrouter}".format(**a) for a in self.application.druid.air]

            if leaf["type"] not in verified_species:
                response, code = yield send_request(
                    branch,
                    "branch/species/{}".format(leaf["type"]),
                    "GET"
                )

                if code == 404:
                    species = yield self.application.async_db.species.find_one({"_id": leaf["type"]})

                    response, code = yield send_request(
                        branch,
                        "branch/species",
                        "POST",
                        species
                    )
                verified_species.add(leaf["type"])

            yield send_post_request(branch, "branch/leaf", leaf)

        self.finish(json.dumps({"result": "success"}))


class LogWatcher(Handler):

    @gen.coroutine
    @token_auth
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
    @token_auth
    def post(self):
        data = json.loads(self.request.body, object_hook=json_util.object_hook)
        yield self.application.druid.propagate_event(data)
        self.finish()
