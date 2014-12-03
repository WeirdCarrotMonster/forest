# -*- coding: utf-8 -*-
"""
Модуль реализует сущность ветви, отвечающую за
запуск приложений, обновление репозиториев и логгирование
процессов.
"""
from __future__ import print_function, unicode_literals

import datetime
from collections import defaultdict
import os

from zmq.eventloop.zmqstream import ZMQStream
import simplejson as json
from bson import ObjectId
from tornado.gen import coroutine, Return
from tornado.ioloop import IOLoop
import zmq

from components.common import log_message
from components.decorators import ignore_autoreconnect
from components.emperor import Emperor
from components.leaf import Leaf
from components.logparse import logparse
from components.species import Species


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

        self.emperor = Emperor(self.trunk.forest_root, self.settings["host"])

        self.species = {}

        self.last_leaves_update = None
        self.last_species_update = None

        ctx = zmq.Context()
        s = ctx.socket(zmq.PULL)
        s.bind('tcp://127.0.0.1:5122')
        self.stream = ZMQStream(s)
        self.stream.on_recv(self.log_message)

    def _push_leaves_update(self, leaf):
        self.last_leaves_update = max([
            self.last_leaves_update or leaf.get("modified"),
            leaf.get("modified")
        ])

    def _push_species_update(self, species):
        self.last_species_update = max([
            self.last_species_update or species.get("modified"),
            species.get("modified")
        ])

    @coroutine
    def log_message(self, message):
        """
        Логгирует входящее сообщение в базе, дополняя информацией о времени,
        компоненте и т.п.

        :param message: Логгируемое сообщение
        :type message: dict
        """
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
    @ignore_autoreconnect
    def periodic_event(self):
        """
        Мониторит коллекцию листьев с целью поиска тех, которые нуждаются в
        запуске/перезапуске/остановке
        """
        query = {
            "batteries": {'$exists': True}
        }
        if self.last_leaves_update:
            query["modified"] = {"$gt": self.last_leaves_update}

        cursor = self.trunk.async_db.leaves.find(query)

        while (yield cursor.fetch_next):
            leaf_data = cursor.next_object()
            self._push_leaves_update(leaf_data)
            leaf = yield self.create_leaf(leaf_data)

            if leaf.running:
                #  Лист запущен в данный момент...
                if not leaf.should_be_running:
                    #  ... но не должен быть запущен:
                    self.del_leaf(leaf)
                elif leaf != self.leaves[leaf.id]:
                    #  .. но его состояние изменилось...
                    if leaf.restarted(self.leaves[leaf.id]):
                        #  ... и не требует изменения конфигурации:
                        self.restart_leaf(leaf)
                    else:
                        #  ... и требует изменения конфигурации:
                        self.del_leaf(leaf)
                        self.add_leaf(leaf)
            else:
                #  Лист не запущен в данный момент...
                if leaf.should_be_running and not leaf.queued:
                    #  ...но должен быть запущен и не ждет запуска:
                    self.add_leaf(leaf)

        query = {"_id": {"$in": self.species.keys()}}
        if self.last_species_update:
            query["modified"] = {"$gt": self.last_species_update}

        cursor = self.trunk.async_db.species.find(query)

        while (yield cursor.fetch_next):
            species = cursor.next_object()
            self._push_species_update(species)

            log_message(
                "Species {} changed".format(species["name"]),
                component="Branch"
            )

            species_new = self.create_specie(species)
            self.species[species["_id"]] = species_new
            yield species_new.initialize()

    @coroutine
    @ignore_autoreconnect
    def task_monitor(self):
        """
        Мониторит коллекцию листьев с целью поиска задач, ожидающих выполнения
        """
        query = {
            "tasks": {"$exists": True},
            "locked": None
        }
        cursor = self.trunk.async_db.leaves.find(query)

        while (yield cursor.fetch_next):
            leaf_data = cursor.next_object()

            locked_leaf = yield self.trunk.async_db.leaves.update(
                {
                    "_id": leaf_data["_id"],
                    "locked": None,
                    "tasks": {
                        "$ne": None
                    }
                },
                {"$set": {"locked": self.trunk.id}}
            )

            if not locked_leaf:
                continue  # Не захватили

            IOLoop.current().spawn_callback(self.do_tasks_async, leaf_data)

    @coroutine
    def do_tasks_async(self, leaf_data):
        """
        Асинхронно выполняет задачи, отмеченные к выполнению на листе

        :param leaf_data: Словарь с данными листа, содержащий информацию о выполняемых задачах
        :type leaf_data: dict
        """
        log_message("Locked leaf {} for task execution".format(leaf_data["_id"]), component="Branch")

        leaf = yield self.create_leaf(leaf_data, need_species_now=True)

        for task in leaf.tasks:
            result, error = yield leaf.species.run_in_env(task, path=leaf.species.src_path, env=leaf.environment)
            yield self.trunk.async_db.logs.insert({
                "component_name": self.trunk.settings["name"],
                "component_type": "branch",
                "log_type": "leaf.task",
                "cmd": task,
                "result": result,
                "error": error
            })

        yield self.trunk.async_db.leaves.update(
            {"_id": leaf_data["_id"]},
            {
                "$set": {"locked": None},
                "$unset": {"tasks": ""}
            }
        )

        log_message("Unlocking leaf {}".format(leaf_data["_id"]), component="Branch")

    @coroutine
    def get_species(self, species_id, now=False):
        """
        Получает экземпляр класса Species, инициализирующегося в фоне, либо ожидает
        окончания его инициализации (поведение определяется параметром now)

        :param species_id: ObjectId вида, получаемого через функцию
        :param now: Флаг необходимости ожидания инициализации вида
        :raise Return: Возвращение результата через tornado coroutines
        :rtype : Species
        """
        if species_id in self.species:
            raise Return(self.species[species_id])

        specie = self.trunk.sync_db.species.find_one({"_id": species_id})

        if not self.last_species_update or self.last_species_update < specie["modified"]:
            self.last_species_update = specie["modified"]

        if specie:
            species_new = self.create_specie(specie)
            if not now:
                IOLoop.current().spawn_callback(species_new.initialize)
            else:
                yield species_new.initialize()

            self.species[species_id] = species_new
            raise Return(self.species[species_id])

        raise Return(None)

    def specie_initialization_finished(self, species):
        """
        Событие, выполняющееся при завершении инициализации вида листьев

        :type species: Species
        :param species: Вид листьев, закончивший инициализацию
        """
        species.is_ready = True
        for leaf in self.leaves.values():
            if leaf.species.id == species.id:
                leaf.specie = species
                self.start_leaf(leaf)

    def load_components(self):
        """
        Загружает компоненты системы
        """
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

    def create_specie(self, species):
        """
        Создает вид листа по данным из словаря

        :rtype : Species
        :param species: словарь с данными конфигурации вида
        :return: Созданный экземпляр вида листа
        """
        return Species(
            ready_callback=self.specie_initialization_finished,
            directory=os.path.join(self.trunk.forest_root, "species"),
            **species
        )

    @coroutine
    def create_leaf(self, leaf, need_species_now=False):
        """
        Создает экземпляр листа  по данным из базы

        :type need_species_now: bool
        :param need_species_now: Флаг ожидания готовности вида
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

        leaf["batteries"] = batteries
        species = yield self.get_species(leaf.get("type"), now=need_species_now)

        raise Return(Leaf(
            keyfile=os.path.join(self.trunk.forest_root, "keys/private.pem"),
            fastrouters=self.fastrouters,
            emperor=self.emperor,
            trunk=self.trunk,
            species=species,
            **leaf
        ))

    def start_leaf(self, leaf):
        """
        Выполняет запуск листа через uwsgi

        :param leaf: Запускаемый лист
        :type leaf: Leaf
        """
        self.emperor.start_leaf(leaf)
        log_message("Starting leaf {}".format(leaf.id), component="Branch")

    def add_leaf(self, leaf):
        """
        Запускает лист и добавляет его в список запущенных

        :type leaf: Leaf
        :param leaf: Словарь настроек листа
        """
        self.leaves[leaf.id] = leaf

        if leaf.species.is_ready:
            self.start_leaf(leaf)
        else:
            log_message("Queued leaf {}".format(leaf.id), component="Branch")

    def del_leaf(self, leaf):
        """
        Останавливает лист и удаляет его из списка листтьев

        :type leaf: Leaf
        :param leaf: Идентификатор листа
        """
        log_message("Stopping leaf {}".format(str(leaf.id)), component="Branch")
        self.emperor.stop_leaf(leaf)
        if leaf.id in self.leaves:
            del self.leaves[leaf.id]

    def restart_leaf(self, leaf):
        """
        Выполняет перезапуск листа и обновляет сохраненную конфигурацию

        :param leaf: Перезапускаемый лист
        :param leaf: Leaf
        """
        log_message("Restarting leaf {}".format(str(leaf.id)), component="Branch")
        self.emperor.soft_restart_leaf(leaf)
        self.leaves[leaf.id] = leaf

    def cleanup(self):
        """
        Принудительно выключает emperor-сервер при остановке
        """
        self.emperor.stop_emperor()
