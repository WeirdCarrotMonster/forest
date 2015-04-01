# -*- coding: utf-8 -*-

from __future__ import unicode_literals, print_function

import random
from datetime import datetime
from itertools import product

from tornado import gen, websocket
from bson import ObjectId
from bson.errors import InvalidId

from forest.components.common import loads, dumps
from forest.components.api.handler import Handler
from forest.components.api.decorators import token_auth, schema
from forest.components.common import send_request
from forest.components.druid.shortcuts import branch_prepare_species, branch_start_leaf, air_enable_host, \
    branch_stop_leaf


# pylint: disable=W0221,W0612


class LeavesHandler(Handler):

    @gen.coroutine
    @token_auth
    def get(self, address=None):
        self.write("[")

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
            self.write(dumps(leaf))
        self.finish("]")

    @gen.coroutine
    @token_auth
    @schema("druid.leaves")
    def post(self, **data):
        """
        Создает новый лист.
        """
        with (yield self.application.druid.creation_lock.acquire()):
            leaf_address_check = yield self.application.async_db.leaves.find_one({
                "$or": [
                    {"address": data["address"]},
                    {"name": data["name"]}
                ]
            })

            if leaf_address_check:
                self.set_status(400)
                self.finish(dumps({
                    "result": "error",
                    "message": "Duplicate address"
                }))
                raise gen.Return()

            try:
                query = {"_id": ObjectId(data["type"])}
            except (TypeError, InvalidId):
                query = {"name": data["type"]}

            species = yield self.application.async_db.species.find_one(query)

            if not species:
                self.set_status(400)
                self.finish(dumps({
                    "result": "error",
                    "message": "Unknown species"
                }))
                raise gen.Return()

            branch = random.choice(self.application.druid.branch)

            leaf_id = yield self.application.async_db.leaves.insert(
                {
                    "name": data["name"],
                    "desc": data.get("description", ""),
                    "type": species["_id"],
                    "active": data.get("start", True),
                    "address": [data["address"]],
                    "branch": branch["name"],
                    "settings": data.get("settings", {})
                }
            )

            yield [air_enable_host(air, data["address"]) for air in self.application.druid.air]

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

                yield self.application.async_db.leaves.update(
                    {"_id": leaf_id},
                    {"$set": {"batteries": db_settings}}
                )
            else:
                pass

            leaf_config = yield self.application.async_db.leaves.find_one({"_id": leaf_id})

            if leaf_config.get("active", True):
                leaf_config["fastrouters"] = ["{host}:{fastrouter}".format(**a) for a in self.application.druid.air]
                leaf_config["uwsgi_mules"] = species.get("uwsgi_mules", [])
                leaf_config["uwsgi_triggers"] = species.get("triggers", {})
                yield branch_prepare_species(branch, species)
                yield branch_start_leaf(branch, leaf_config)

            self.finish(dumps({"result": "success", "message": "OK", "branch": branch["name"]}))


class LeafHandler(Handler):

    @gen.coroutine
    @token_auth
    def get(self, leaf_name):
        leaf_data = yield self.application.async_db.leaves.find_one({"name": leaf_name})

        if not leaf_data:
            self.set_status(404)
            self.finish("")
        else:
            self.finish(dumps(leaf_data))

    @gen.coroutine
    @token_auth
    def patch(self, leaf_name):
        # Обрабатываем только ключи active, address
        apply_changes = self.get_argument("apply", default="TRUE").upper() == "TRUE"

        keys = ["active", "address"]
        data = loads(self.request.body)

        for key in data.keys():
            if key not in keys:
                del data[key]

        leaf_data = yield self.application.async_db.leaves.find_one({"name": leaf_name})
        if not leaf_data:
            self.set_status(404)
            self.finish(dumps({"result": "failure", "message": "Unknown leaf"}))
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
                leaf_data["fastrouters"] = ["{host}:{fastrouter}".format(**a) for a in self.application.druid.air]
                leaf_data["uwsgi_mules"] = species.get("uwsgi_mules", [])
                leaf_data["uwsgi_triggers"] = species.get("triggers", {})

                yield branch_prepare_species(branch, species)
                yield branch_start_leaf(branch, leaf_data)

                yield [
                    air_enable_host(air, address) for air, address in product(
                        self.application.druid.air,
                        leaf_data["address"]
                    )
                ]
            else:
                branch = next(x for x in self.application.druid.branch if x["name"] == leaf_data["branch"])
                yield branch_stop_leaf(branch, leaf_data)
        self.finish(dumps({"result": "success", "message": "OK"}))


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

        self.finish(dumps(leaf_status))


class SpeciesListHandler(Handler):

    @gen.coroutine
    @token_auth
    def get(self):
        cursor = self.application.async_db.species.find()
        self.write("[")
        species = None
        while (yield cursor.fetch_next):
            if species:
                self.write(",")

            species = cursor.next_object()
            self.write(dumps({
                "_id": species["_id"],
                "name": species["name"]
            }))
        self.finish("]")


class TracebackHandler(Handler):

    @gen.coroutine
    @token_auth
    def get(self, traceback_id):
        traceback = yield self.application.async_db.logs.find_one({
            "log_type": "leaf.traceback",
            "traceback_id": traceback_id
        })

        self.set_status(200 if traceback else 404)
        self.finish(dumps(traceback))


class SpeciesHandler(Handler):

    @gen.coroutine
    @token_auth
    def get(self, species_id):
        _id = ObjectId(species_id)
        species = yield self.application.async_db.species.find_one({"_id": _id})

        self.set_status(200 if species else 404)
        self.finish(dumps(species))

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

        yield [send_request(
            branch,
            "branch/species/{}".format(species["_id"]),
            "PATCH",
            species
        ) for branch in self.application.druid.branch]

        self.finish("{}")


class BranchHandler(Handler):

    @gen.coroutine
    @token_auth
    def get(self, branch_name=None):
        if branch_name:
            self.finish("{}")
        else:
            self.finish(dumps([x["name"] for x in self.application.druid.branch]))

    @gen.coroutine
    @token_auth
    def put(self, branch_name=None):
        assert branch_name
        try:
            branch = next(x for x in self.application.druid.branch if x["name"] == branch_name)
        except StopIteration:
            self.set_status(404)
            self.finish()
            raise gen.Return()

        cursor = self.application.async_db.leaves.find({"branch": branch_name, "active": True})

        verified_species = set()

        while (yield cursor.fetch_next):
            leaf = cursor.next_object()

            species = yield self.application.async_db.species.find_one({"_id": leaf["type"]})
            leaf["fastrouters"] = ["{host}:{fastrouter}".format(**a) for a in self.application.druid.air]
            leaf["uwsgi_mules"] = species.get("uwsgi_mules", [])
            leaf["uwsgi_triggers"] = species.get("triggers", {})

            if leaf["type"] not in verified_species:
                yield branch_prepare_species(branch, species)
                verified_species.add(leaf["type"])

            yield branch_start_leaf(branch, leaf)

        self.finish(dumps({"result": "success"}))


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
            self.write(dumps(data))
            self.flush()


class WebsocketLogWatcher(websocket.WebSocketHandler):

    def check_origin(self, origin):
        return True

    def open(self, leaf_name):
        self.subscribed = False

        self.leaf_data = self.application.sync_db.leaves.find_one({"name": leaf_name})

        if not self.leaf_data:
            self.close()
            return

        if self.application.secret == self.request.headers.get("Token"):
            self.subscribe_logger()

    def on_message(self, message):
        parsed = loads(message)

        if "Token" in parsed and self.application.secret == parsed["Token"]:
            self.subscribe_logger()

    def subscribe_logger(self):
        if self.subscribed:
            return

        self.application.druid.add_listener(self.leaf_data["_id"], self)
        self.subscribed = True

    def on_close(self):
        if self.subscribed:
            self.application.druid.remove_listener(self.leaf_data["_id"], self)

    def put(self, data):
        self.write_message(dumps(data))


class LogHandler(Handler):

    @gen.coroutine
    @token_auth
    def post(self):
        data = loads(self.request.body)
        yield self.application.druid.propagate_event(data)
        self.finish()
