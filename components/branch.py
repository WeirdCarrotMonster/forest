# -*- coding: utf-8 -*-
"""
Модуль реализует сущность ветви, отвечающую за
запуск приложений, обновление репозиториев и логгирование
процессов.
"""
from __future__ import print_function, unicode_literals

import datetime
from collections import defaultdict
from zmq.eventloop.zmqstream import ZMQStream

import simplejson as json
from bson import ObjectId

from components.common import log_message
from components.database import get_default_database
from components.emperor import Emperor
from components.leaf import Leaf
from components.logparse import logparse
from components.specie import Specie
from tornado.gen import coroutine
import zmq


class Branch(object):
    """
    Класс ветви, служащий для запуска приложений и логгирования их вывода
    """
    def __init__(self, settings, trunk):
        self.settings = settings
        self.trunk = trunk
        self.leaves = {}

        self.load_components()

        self.emperor = Emperor(self.settings["emperor_dir"])

        self.species = {}

        self.last_update = None

        ctx = zmq.Context()
        s = ctx.socket(zmq.PULL)
        s.bind('tcp://127.0.0.1:5122')
        self.stream = ZMQStream(s)
        self.stream.on_recv(self.log_message)

        self.fastrouters = []
        self.batteries = defaultdict(list)

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

            trunk = get_default_database(self.trunk.settings, async=True)
            yield trunk.logs.insert(data_parsed)

    def periodic_event(self):
        trunk = get_default_database(self.trunk.settings, async=True)
        query = {"batteries": {'$exists': True}}
        if self.last_update:
            query["modified"] = {"$gt": self.last_update}

        cursor = trunk.leaves.find(query)
        cursor.each(callback=self._found_leaf)

    def _found_leaf(self, result, error):
        if not result:
            return

        if not self.last_update or self.last_update < result.get("modified"):
            self.last_update = result.get("modified")
        _id = result.get("_id")

        if self.trunk.settings["id"] not in result.get("branch"):
            if _id in self.leaves.keys():
                self.del_leaf(_id)
        else:
            if result.get("active", False):
                leaf = self.create_leaf(result)
                self.add_leaf(leaf)
            elif _id in self.leaves.keys():
                self.del_leaf(_id)

    def get_specie(self, specie_id):
        if specie_id in self.species:
            return self.species[specie_id]

        trunk = get_default_database(self.trunk.settings)

        spc = trunk.species.find_one({"_id": specie_id})

        if spc:
            specie_new = Specie(
                directory=self.settings["species"],
                specie_id=specie_id,
                name=spc.get("name"),
                url=spc.get("url"),
                last_update=spc.get("last_update"),
                triggers=spc.get("triggers", {}),
                ready_callback=self.specie_initialization_finished,
                modified=spc["modified"]
            )
            specie_new.initialize()

            self.species[specie_id] = specie_new
            return self.species[specie_id]

        return None

    def specie_initialization_finished(self, specie):
        specie.is_ready = True
        for leaf in self.leaves.values():
            if leaf.specie == specie:
                self.start_leaf(leaf)

    def load_components(self):
        trunk = get_default_database(self.trunk.settings)
        components = trunk.components
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
            specie=self.get_specie(leaf.get("type"))
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
