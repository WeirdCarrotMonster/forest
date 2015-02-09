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
from toro import Lock

from components.common import log_message, send_request

from components.leaf import Leaf
from components.logparse import logparse
from components.species import Species


class Branch(object):

    """
    Класс ветви, служащий для запуска приложений и логгирования их вывода
    """

    def __init__(self, trunk, settings):
        self.__host__ = settings.get("host", "127.0.0.1")
        self.trunk = trunk

        self.leaves = {}
        self.species = {}

        self.__loggers__ = settings.get("loggers")
        self.batteries = defaultdict(list)

        ctx = zmq.Context()
        s = ctx.socket(zmq.PULL)
        s.bind('tcp://127.0.0.1:5122')
        self.stream = ZMQStream(s)
        self.stream.on_recv(self.log_message)
        log_message("Started branch", component="Branch")

        self.species_lock = Lock()

    @coroutine
    def log_message(self, message):
        """
        Логгирует входящее сообщение в базе, дополняя информацией о времени,
        компоненте и т.п.

        :param message: Логгируемое сообщение
        :type message: list
        """
        for data in message:
            data = data.strip()

            if not data:
                continue

            add_info = {
                "component_name": self.trunk.name,
                "component_type": "branch",
                "log_type": "leaf.event"
            }

            try:
                data_parsed = json.loads(data)
                data_parsed.update(add_info)
                data_parsed["time"] = datetime.datetime.utcfromtimestamp(int(data_parsed["time"]))
                data_parsed["msecs"] = int(data_parsed["msecs"])
                data_parsed["status"] = int(data_parsed["status"])
                data_parsed["request_size"] = int(data_parsed["request_size"])
                data_parsed["response_size"] = int(data_parsed["response_size"])

            except json.JSONDecodeError:
                data_parsed, important = logparse(data)
                data_parsed["time"] = datetime.datetime.utcnow()

            data_parsed["component_type"] = "branch"
            if "log_source" in data_parsed:
                data_parsed["log_source"] = ObjectId(data_parsed["log_source"])

            for logger in self.__loggers__:
                yield send_request(
                    logger,
                    logger["resource"],
                    "POST",
                    data_parsed
                )

    def get_species(self, species_id):
        """
        Получает экземпляр класса Species

        :param species_id: ObjectId вида, получаемого через функцию
        :raise Return: Возвращение результата через tornado coroutines
        :rtype : Species
        """
        if species_id in self.species:
            return self.species[species_id]
        else:
            return None

    def create_species(self, species):
        """
        Создает вид листа по данным из словаря

        :rtype : Species
        :param species: словарь с данными конфигурации вида
        :return: Созданный экземпляр вида листа
        """
        species = Species(
            ready_callback=self.__species_initialization_finished__,
            directory=os.path.join(self.trunk.forest_root, "species"),
            **species
        )

        if species.id in self.species:
            log_message("Updating species {}".format(species.id), component="Branch")
        else:
            log_message("Creating species {}".format(species.id), component="Branch")

        self.species[species.id] = species

        self.__species_initialization_started__(species)
        IOLoop.current().spawn_callback(species.initialize)

    def __species_initialization_started__(self, species):
        for leaf in self.leaves.values():
            if leaf.species.id == species.id:
                leaf.species = species
                leaf.stop()

    def __species_initialization_finished__(self, species):
        """
        Событие, выполняющееся при завершении инициализации вида листьев

        :type species: Species
        :param species: Вид листьев, закончивший инициализацию
        """
        species.is_ready = True
        for leaf in self.leaves.values():
            if leaf.species.id == species.id:
                leaf.species = species
                leaf.start()

    @coroutine
    def create_leaf(self, leaf):
        """
        Создает экземпляр листа  по данным из базы

        :type need_species_now: bool
        :param need_species_now: Флаг ожидания готовности вида
        :type leaf: dict
        :param leaf: Словарь с конфигурацией листа
        :rtype: Leaf
        :return: Созданный по данным базы экземпляр листа
        """
        species = self.get_species(leaf.get("type"))
        if not species:
            raise Return(None)
        l = Leaf(
            keyfile=os.path.join(self.trunk.forest_root, "keys/private.pem"),
            emperor=self.trunk.emperor,
            species=species,
            log_port=5122,
            leaf_host=self.__host__,
            **leaf
        )
        raise Return(l)

    def add_leaf(self, leaf):
        if leaf.id in self.leaves:
            self.leaves[leaf.id].stop()
            del self.leaves[leaf.id]

        self.leaves[leaf.id] = leaf
        return leaf.start()

    def del_leaf(self, leaf):
        leaf.stop()
        if leaf.id in self.leaves:
            del self.leaves[leaf.id]
