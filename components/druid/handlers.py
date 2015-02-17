# -*- coding: utf-8 -*-

from __future__ import unicode_literals, print_function

import random
from datetime import datetime

from tornado import gen
import simplejson as json
from bson import ObjectId, json_util

from components.api.handler import Handler
from components.api.decorators import token_auth
from components.common import send_request
from components.druid.shortcuts import branch_prepare_species, branch_start_leaf, air_enable_host, branch_stop_leaf


class LeavesHandler(Handler):

    @gen.coroutine
    @token_auth
    def get(self):
        self.write("[")

        address = self.get_argument("address", None, True)

        if address:
            query = {"address": address}
        else:
            query = {}

        cursor = self.application.async_db.leaves.find(
            query,
            {
                "name": True
            }
        )
        first = True
        while (yield cursor.fetch_next):
            if not first:
                self.write(",")
            else:
                first = False

            leaf = cursor.next_object()
            self.write(json.dumps(leaf, default=json_util.default))
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
            self.set_status(400)
            self.finish(json.dumps({
                "result": "error",
                "message": "Duplicate name"
            }))
            raise gen.Return()

        leaf_id = leaf["upserted"]

        try:
            query = {"_id": ObjectId(leaf_type)}
        except:
            query = {"name": leaf_type}

        species = yield self.application.async_db.species.find_one(query)

        if not species:
            self.set_status(400)
            self.finish(json.dumps({
                "result": "error",
                "message": "Unknown species"
            }))
            raise gen.Return()

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

        for air in self.application.druid.air:
            yield air_enable_host(air, leaf_address)

        if species.get("requires", []):
            roots = self.application.druid.roots[0]
            db_settings, code = yield send_request(
                roots,
                "roots/db",
                "POST",
                {
                    "name": leaf_id,
                    "db_type": species["requires"]
                }
            )

            yield self.application.async_db.leaves.update({"_id": leaf_id}, {"$set": {"batteries": db_settings}})
        else:
            db_settings = {}

        branch = random.choice(self.application.druid.branch)

        yield self.application.async_db.leaves.update({"_id": leaf_id}, {"$set": {"branch": branch["name"]}})

        leaf_config = yield self.application.async_db.leaves.find_one({"_id": leaf_id})
        leaf_config["fastrouters"] = ["{host}:{fastrouter}".format(**a) for a in self.application.druid.air]

        # ==============
        # Проверяем наличие искомого типа на ветви
        # ==============

        yield branch_prepare_species(branch, species)
        yield branch_start_leaf(branch, leaf_config)

        self.finish(json.dumps({"result": "success", "message": "OK"}))


class LeafHandler(Handler):

    @gen.coroutine
    @token_auth
    def get(self, leaf_name):
        leaf_data = yield self.application.async_db.leaves.find_one({"name": leaf_name})

        if not leaf_data:
            self.set_status(404)
            self.finish("")
            return

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

                leaf_data["fastrouters"] = [
                    "{host}:{fastrouter}".format(**a) for a in self.application.druid.air
                ]

                species = yield self.application.async_db.species.find_one({"_id": leaf_data["type"]})

                yield branch_prepare_species(branch, species)
                yield branch_start_leaf(branch, leaf_data)

                for air in self.application.druid.air:
                    for address in leaf_data["address"]:
                        yield air_enable_host(air, address)
            else:
                branch = next(x for x in self.application.druid.branch if x["name"] == leaf_data["branch"])
                yield branch_stop_leaf(branch, leaf_data)
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


class SpeciesListHandler(Handler):

    @gen.coroutine
    @token_auth
    def get(self):
        cursor = self.application.async_db.species.find()
        self.write("[")
        first = True
        while (yield cursor.fetch_next):
            if not first:
                self.write(",")
            else:
                first = False

            species = cursor.next_object()
            self.write(json.dumps({
                "_id": species["_id"],
                "name": species["name"]
            }, default=json_util.default))
        self.finish("]")


class TracebackHandler(Handler):

    @gen.coroutine
    @token_auth
    def get(self, traceback_id):
        traceback = yield self.application.async_db.logs.find_one({
            "log_type": "leaf.traceback",
            "traceback_id": traceback_id
        })

        if not traceback:
            self.set_status(404)
            self.finish("")
            return

        self.finish(json.dumps(traceback, default=json_util.default))


class SpeciesHandler(Handler):

    @gen.coroutine
    @token_auth
    def get(self, species_id):
        _id = ObjectId(species_id)
        species = yield self.application.async_db.species.find_one({"_id": _id})

        if not species:
            self.set_status(404)

        self.finish(json.dumps(species, default=json_util.default))

    @gen.coroutine
    @token_auth
    def patch(self, species_id):
        _id = ObjectId(species_id)

        species = yield self.application.async_db.species.find_one({"_id": _id})

        if not species:
            self.set_status(404)
            self.finish("{}")
            raise gen.Return()

        yield self.application.async_db.species.update(
            {"_id": _id},
            {"$set": {"modified": datetime.utcnow()}}
        )

        species = yield self.application.async_db.species.find_one({"_id": _id})

        for branch in self.application.druid.branch:
            yield send_request(
                branch,
                "branch/species/{}".format(species["_id"]),
                "PATCH",
                species
            )

        self.finish("{}")


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
            self.set_status(404)
            self.finish()
            raise gen.Return()

        cursor = self.application.async_db.leaves.find({"branch": branch_name, "active": True})

        verified_species = set()

        while (yield cursor.fetch_next):
            leaf = cursor.next_object()

            leaf["fastrouters"] = ["{host}:{fastrouter}".format(**a) for a in self.application.druid.air]

            if leaf["type"] not in verified_species:
                species = yield self.application.async_db.species.find_one({"_id": leaf["type"]})
                yield branch_prepare_species(branch, species)
                verified_species.add(leaf["type"])

            yield branch_start_leaf(branch, leaf)

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
