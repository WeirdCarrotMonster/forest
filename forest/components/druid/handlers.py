# coding=utf-8
"""Описывает хендлеры для работы внешнего API леса."""

from __future__ import unicode_literals, print_function

import random
from datetime import datetime
from itertools import product

from tornado import gen, websocket
from bson import ObjectId
from bson.errors import InvalidId

from forest.jsonschema.decorators import schema

from forest.components.common import loads, dumps
from forest.components.api.handler import Handler
from forest.components.api.decorators import token_auth
from forest.components.common import send_request
from forest.components.druid.shortcuts import branch_prepare_species, branch_start_leaf, air_enable_host, \
    branch_stop_leaf, full_leaf_info


# pylint: disable=W0221,W0612


class LeavesHandler(Handler):

    @gen.coroutine
    @token_auth
    def get(self, address=None):
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

        self.write("[")
        leaf = None
        while (yield cursor.fetch_next):
            if leaf:
                self.write(",")

            leaf = cursor.next_object()
            self.write(dumps(leaf))
        self.finish("]")

    @gen.coroutine
    @token_auth
    @schema("druid.leaves")
    def post(self, **data):
        """Создает новый лист."""
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

            leaf = yield self.application.async_db.leaves.find_one({"_id": leaf_id})

            if leaf.get("active", True):
                leaf = full_leaf_info(leaf, self.application.druid.air, species)

                yield branch_prepare_species(branch, species)
                yield branch_start_leaf(branch, leaf)

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

        leaf = yield self.application.async_db.leaves.find_one({"name": leaf_name})

        if apply_changes:
            if leaf["active"]:
                branch = next(x for x in self.application.druid.branch if x["name"] == leaf["branch"])

                species = yield self.application.async_db.species.find_one({"_id": leaf["type"]})

                leaf = full_leaf_info(leaf, self.application.druid.air, species)

                yield branch_prepare_species(branch, species)
                yield branch_start_leaf(branch, leaf)

                yield [
                    air_enable_host(air, address) for air, address in product(
                        self.application.druid.air,
                        leaf["address"]
                    )
                ]
            else:
                branch = next(x for x in self.application.druid.branch if x["name"] == leaf["branch"])
                yield branch_stop_leaf(branch, leaf)
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

        if species:
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

            cursor = self.application.async_db.leaves.find({"type": species["_id"], "active": True})
            while (yield cursor.fetch_next):
                leaf = full_leaf_info(cursor.next_object(), self.application.druid.air, species)
                branch = next(x for x in self.application.druid.branch if x["name"] == leaf["branch"])
                yield branch_start_leaf(branch, leaf)
        else:
            self.set_status(404)

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
        """Выполняет принудительную проверку всех листьев на указанной ветви.

        :param branch_name: Имя ветви
        :type branch_name: str
        """
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
            leaf = full_leaf_info(leaf, self.application.druid.air, species)

            if leaf["type"] not in verified_species:
                yield branch_prepare_species(branch, species)
                verified_species.add(leaf["type"])

            yield branch_start_leaf(branch, leaf)

        self.finish(dumps({"result": "success"}))


class WebsocketLogWatcher(websocket.WebSocketHandler):

    """Хендлер клиентов, ожидающих логи по websocket-протоколу."""

    def check_origin(self, *args, **kwargs):
        """Отключает проверку origin."""
        return True

    def open(self, leaf):
        """Открывает подключение и регистрирует логгер.

        :param leaf: Лист, логи которого передаются клиенту
        :type leaf: str
        """
        if self.application.secret != self.request.headers.get("Token"):
            self.write_message(dumps({
                "result": "error",
                "message": "Not authenticated"
            }))
            self.close()
            return

        self.leaf = leaf
        self.application.druid.add_listener(self.leaf, self)

    def on_close(self):
        """Обработчик события закрытия подключения."""
        try:
            self.application.druid.remove_listener(self.leaf, self)
        except AttributeError:
            pass

    def put(self, data):
        """Отправляет лог клиенту.

        :param data: Передаваемый лог
        :type data: dict
        """
        self.write_message(dumps(data))


class LogHandler(Handler):

    """Хендлер логов, поступающих от других нод."""

    @gen.coroutine
    @token_auth
    @schema()
    def post(self, **data):
        """Сохраняет данные лога в базу.

        Предполагается, что логи всегда поступают в виде json-словаря и разбираются в декораторе schema().
        :param data: Словарь с данными.
        :type data: dict
        """
        yield self.application.druid.propagate_event(data)
        self.finish()
