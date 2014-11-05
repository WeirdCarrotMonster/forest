# -*- coding: utf-8 -*-
"""
Модуль реализует сущность ветви, отвечающую за
запуск приложений, обновление репозиториев и логгирование
процессов.
"""
from __future__ import print_function, unicode_literals

import datetime
from collections import defaultdict

from tornado.web import asynchronous
from zmq.eventloop.zmqstream import ZMQStream
import simplejson as json
from bson import ObjectId
from tornado.gen import coroutine
import zmq

from components.common import log_message
from components.emperor import Emperor

from components.leaf import Leaf
from components.logparse import logparse
from components.specie import Specie


class Branch(object):
    """
    Класс ветви, служащий для запуска приложений и логгирования их вывода
    """
    def __init__(self, settings, trunk):
        self.settings = settings
        self.trunk = trunk
        self.leaves = {}

        self.fastrouters = []
        self.batteries = defaultdict(list)

        self.load_components()

        self.emperor = Emperor(self.settings["emperor_dir"])

        self.species = {}

        self.last_leaves_update = None
        self.last_species_update = None

        ctx = zmq.Context()
        s = ctx.socket(zmq.PULL)
        s.bind('tcp://127.0.0.1:5122')
        self.stream = ZMQStream(s)
        self.stream.on_recv(self.log_message)

    def _push_leaves_update(self, leaf):
        if not self.last_leaves_update or self.last_leaves_update < leaf.get("modified"):
            self.last_leaves_update = leaf.get("modified")

    @coroutine
    def log_message(self, message):
        for data in message:
            data = data.strip()

            add_info = {
                "component_name": self.trunk.settings["name"],
                "component_type": "branch",
                "log_type": "leaf.event"
            }

            if not data:
                return
            try:
                data_parsed = json.loads(data)
                data_parsed.update(add_info)
                data_parsed["status"] = int(data_parsed["status"])
                data_parsed["msecs"] = int(data_parsed["msecs"])
                data_parsed["size"] = int(data_parsed["size"])

            except json.JSONDecodeError:
                data_parsed, important = logparse(data)

            data_parsed["component_name"] = self.trunk.settings["id"]
            data_parsed["component_type"] = "branch"
            data_parsed["added"] = datetime.datetime.now()
            if "log_source" in data_parsed:
                data_parsed["log_source"] = ObjectId(data_parsed["log_source"])

            yield self.trunk.async_db.logs.insert(data_parsed)

    @coroutine
    def periodic_event(self):
        query = {"batteries": {'$exists': True}}
        if self.last_leaves_update:
            query["modified"] = {"$gt": self.last_leaves_update}

        cursor = self.trunk.async_db.leaves.find(query)

        while (yield cursor.fetch_next):
            leaf = cursor.next_object()
            self._push_leaves_update(leaf)
            _id = leaf.get("_id")

            try:
                if self.trunk.settings["id"] not in leaf.get("branch"):
                    if _id in self.leaves.keys():
                        self.del_leaf(_id)
                else:
                    if leaf.get("active", False):
                        leaf = self.create_leaf(leaf)
                        self.add_leaf(leaf)
                    elif _id in self.leaves.keys():
                        self.del_leaf(_id)
            except KeyError:
                pass

        query = {"_id": {"$in": self.species.keys()}}
        if self.last_species_update:
            query["modified"] = {"$gt": self.last_species_update}

        cursor = self.trunk.async_db.species.find(query)

        while (yield cursor.fetch_next):
            species = cursor.next_object()
            log_message(
                "Species {} changed".format(species["name"]),
                component="Branch"
            )

            species_new = self.create_specie(species)
            self.species[species["_id"]] = species_new

            if not self.last_species_update or self.last_species_update < species["modified"]:
                self.last_species_update = species["modified"]

            species_new.initialize()

    def get_species(self, species_id):
        if species_id in self.species:
            return self.species[species_id]

        specie = self.trunk.sync_db.species.find_one({"_id": species_id})

        if not self.last_species_update or self.last_species_update < specie["modified"]:
            self.last_species_update = specie["modified"]

        if specie:
            specie_new = self.create_specie(specie)
            specie_new.initialize()

            self.species[species_id] = specie_new
            return self.species[species_id]

        return None

    def specie_initialization_finished(self, specie):
        specie.is_ready = True
        for leaf in self.leaves.values():
            if leaf.specie.id == specie.id:
                leaf.specie = specie
                self.start_leaf(leaf)

    def load_components(self):
        components = self.trunk.sync_db.components
        for component in components.find({"roles.air": {"$exists": True}}):
            host = component["host"]
            port = component["roles"]["air"]["fastrouter"]
            self.fastrouters.append("{0}:{1}".format(host, port))

        for component in components.find({"roles.roots.mysql": {"$exists": True}}):
            self.batteries["mysql"].append(
                (
                    component["roles"]["roots"]["mysql"]["host"],
                    component["roles"]["roots"]["mysql"]["port"]
                )
            )

        for component in components.find({"roles.roots.mongo": {"$exists": True}}):
            self.batteries["mongo"].append(
                (
                    component["roles"]["roots"]["mongo"]["host"],
                    component["roles"]["roots"]["mongo"]["port"]
                )
            )

    def create_specie(self, specie):
        return Specie(
            directory=self.settings["species"],
            specie_id=specie["_id"],
            name=specie["name"],
            url=specie["url"],
            triggers=specie.get("triggers", {}),
            ready_callback=self.specie_initialization_finished,
            modified=specie["modified"]
        )

    def create_leaf(self, leaf):
        """
        Создает экземпляр листа  по данным из базы

        :type leaf: dict
        :param leaf: Словарь с конфигурацией листа
        :rtype: Leaf
        :return: Созданный по данным базы экземпляр листа
        """
        batteries = leaf.get("batteries", {})
        for key, value in batteries.items():
            if key in self.batteries:
                batteries[key]["host"] = self.batteries[key][0][0]
                batteries[key]["port"] = self.batteries[key][0][1]

        new_leaf = Leaf(
            name=leaf["name"],
            _id=leaf.get("_id"),
            host=self.settings["host"],
            settings=leaf.get("settings", {}),
            fastrouters=self.fastrouters,
            keyfile=self.settings.get("keyfile", None),
            address=leaf.get("address"),
            component=self.trunk.settings["name"],
            batteries=batteries,
            workers=leaf.get("workers", 4),
            threads=leaf.get("threads", False),
            specie=self.get_species(leaf.get("type"))
        )
        return new_leaf

    def start_leaf(self, leaf):
        self.emperor.start_leaf(leaf)
        log_message(
            "Starting leaf {}".format(leaf.id),
            component="Branch"
        )

    def add_leaf(self, leaf):
        """
        Запускает лист и добавляет его в список запущенных

        :type leaf: Leaf
        :param leaf: Словарь настроек листа
        """
        self.leaves[leaf.id] = leaf

        if leaf.specie.is_ready:
            self.start_leaf(leaf)
        else:
            log_message(
                "Queued leaf {}".format(leaf.id),
                component="Branch"
            )

    def del_leaf(self, _id):
        """
        Останавливает лист и удаляет его из списка активных

        :type _id: ObjectId
        :param _id: Идентификатор листа
        """
        log_message(
            "Stopping leaf {}".format(str(_id)),
            component="Branch"
        )
        self.emperor.stop_leaf(self.leaves[_id])
        del self.leaves[_id]

    def cleanup(self):
        """
        Метод выключения листьев при остановке.
        """
        self.emperor.stop_emperor()
