# coding=utf-8
"""Модуль реализует сущность ветви.

Ветвь отвечает за запуск приложений, обновление репозиториев и логгирование процессов.
"""
from __future__ import print_function, unicode_literals

import datetime
import traceback
from collections import defaultdict
import os

from zmq.eventloop.zmqstream import ZMQStream
from tornado.gen import coroutine, Return
from tornado.ioloop import IOLoop
import simplejson as json
import ConfigParser
import zmq

from forest.components.common import log_message

from forest.components.leaf import Leaf
from forest.components.logparse import logparse
from forest.components.species import Species
from forest.components.common import loads, load
from forest.components.branch.loggers import Logger, POSTLogger


# pylint: disable=W0702,W0612,W0613


class Branch(object):

    """Класс ветви, служащий для запуска приложений и логгирования их работы."""

    def __init__(self, trunk, settings):
        """Инициализирует ветвь.

        :param trunk: корневой объект ноды леса.
        :type trunk: Trunk
        :param settings: Настройки ветви
        :type settings: dict
        """
        self.__host__ = settings.get("host", "127.0.0.1")
        self.trunk = trunk

        self.leaves = {}
        self.species = {}
        self.__loggers__ = []

        for logger in settings.get("loggers", []):
            try:
                self.add_logger(logger)
            except Logger.LoggerCreationError as e:
                log_message("Error adding '{}': {}".format(logger.get("identifier"), e.message), component="Branch")

        self.batteries = defaultdict(list)

        ctx = zmq.Context()
        s = ctx.socket(zmq.PULL)
        s.bind('tcp://127.0.0.1:5122')
        self.stream = ZMQStream(s)
        self.stream.on_recv(self.log_message)
        log_message("Started branch", component="Branch")

        IOLoop.current().spawn_callback(self.__restore_species__)

    @coroutine
    def __restore_species__(self):
        """Выполняет восстановление видов после перезагрузки."""
        try:
            for species_id in os.listdir(self.species_dir):
                if os.path.isdir(os.path.join(self.species_dir, species_id)):
                    try:
                        with open(os.path.join(self.species_dir, species_id, "metadata.json"), "r") as m:
                            yield self.create_species(load(m), initialize=False)
                    except (TypeError, ValueError, IOError):
                        pass
        except OSError:
            pass

        IOLoop.current().spawn_callback(self.__restore_leaves__)

    @coroutine
    def __restore_leaves__(self):
        """Выполняет восстановление листьев после перезагрузки."""
        for leaf_config in os.listdir(self.trunk.emperor.vassal_dir):
            config = ConfigParser.ConfigParser()
            config.read(os.path.join(self.trunk.emperor.vassal_dir, leaf_config))
            try:
                data = loads(config.get("forest", "data"))

                if data.get("cls") != "Leaf":
                    continue

                try:
                    leaf = self.create_leaf(**data)
                except (TypeError, ValueError):
                    pass

                if leaf:
                    log_message("Restoring leaf {}".format(leaf.id), component="Branch")
                    self.add_leaf(leaf, start=False)
            except (ConfigParser.NoSectionError, ConfigParser.NoOptionError, Species.NotDefined):
                continue

    @property
    def species_dir(self):
        """Генерирует полный путь к директории видов.

        :returns: Полный путь к директории видов
        :rtype: str
        """
        return os.path.join(self.trunk.forest_root, "species")

    @coroutine
    def log_message(self, message):
        """Логгирует входящее сообщение в базе, дополняя информацией о времени, компоненте и т.п.

        :param message: Логгируемое сообщение
        :type message: list
        """
        for data in (_.strip() for _ in message if _.strip()):
            try:
                data_parsed = loads(data)
                try:
                    data_parsed["time"] = datetime.datetime.utcfromtimestamp(int(data_parsed["time"]))
                except KeyError:
                    data_parsed["time"] = datetime.datetime.utcnow()
                except ValueError:
                    pass

                for key in ["msecs", "status", "request_size", "response_size"]:
                    if key in data_parsed:
                        data_parsed[key] = int(data_parsed[key])

                data_parsed["log_type"] = "leaf.event"
            except json.JSONDecodeError:
                data_parsed = logparse(data)
                data_parsed["time"] = datetime.datetime.utcnow()

            data_parsed.update({
                "component_name": self.trunk.name,
                "component_type": "branch"
            })

            try:
                yield [logger.log(data_parsed) for logger in self.__loggers__ if logger.suitable(data_parsed)]
            except:
                traceback.print_exc()

        failed_loggers = [logger for logger in self.__loggers__ if logger.failed]

        for logger in failed_loggers:
            self.__loggers__.remove(logger)

    def add_logger(self, configuration):
        """Добавляет логгер заданной конфигурации.

        :param configuration: Конфигурация активируемого логгера
        :type configuration: dict
        :raise LoggerCreationError: ошибка создания логгера
        """
        for logger in self.__loggers__:
            if logger.identifier == configuration["identifier"]:
                raise Logger.LoggerCreationError("Duplicate identifier")

        if configuration.get("type") == "POSTLogger":
            try:
                self.__loggers__.append(POSTLogger(**configuration))
            except TypeError:
                raise Logger.LoggerCreationError("Invalid logger configuration")
        else:
            raise Logger.LoggerCreationError("Unknown logger type")

    def delete_logger(self, identifier):
        """Удаляет логгер с указанным идентификатором.

        :param identifier: Идентификатор логгера
        :type identifier: str
        :returns: Результат удаления логгера
        :rtype: tuple
        """
        try:
            logger = next(x for x in self.__loggers__ if x.identifier == identifier)
            self.__loggers__.remove(logger)
        except StopIteration:
            return False, 404, "Not found"
        except Exception as e:
            return False, 500, str(e)
        else:
            return True, 200, "OK"

    @coroutine
    def create_species(self, species, initialize=True):
        """Создает вид листа по данным из словаря.

        :rtype : Species
        :param species: словарь с данными конфигурации вида
        :return: Созданный экземпляр вида листа
        """
        species = Species(
            directory=os.path.join(self.trunk.forest_root, "species"),
            **species
        )

        if species.id in self.species:
            log_message("Updating species {}".format(species.id), component="Branch")
        elif initialize:
            log_message("Creating species {}".format(species.id), component="Branch")
        else:
            log_message("Restoring species {}".format(species.id), component="Branch")

        self.species[species.id] = species

        if initialize:

            species.is_ready = False
            for leaf in (_ for _ in self.leaves.values() if _.species.id == species.id):
                leaf.species = species
                leaf.pause()

            yield species.initialize()

            species.is_ready = True
            for leaf in (_ for _ in self.leaves.values() if _.species.id == species.id):
                leaf.species = species
                leaf.start()

        raise Return(species)

    def create_leaf(self, **leaf):
        """Создает экземпляр листа.

        :type leaf: dict
        :param leaf: Словарь с конфигурацией листа
        :rtype: Leaf
        :return: Созданный по данным базы экземпляр листа
        """
        species = self.species.get(leaf.get("type"))
        if not species:
            raise Species.NotDefined()

        return Leaf(
            keyfile=os.path.join(self.trunk.forest_root, "keys", "private.pem"),
            emperor=self.trunk.emperor,
            species=species,
            log_port=5122,
            leaf_host=self.__host__,
            **leaf
        )

    def add_leaf(self, leaf, start=True):
        """Добавляет лист на ветвь.

        :param leaf: Лист
        :type leaf: Leaf
        :param start: Флаг запуска
        :type start: bool
        :returns: Результат запуска
        :rtype: bool
        """
        if leaf.id in self.leaves:
            self.leaves[leaf.id].stop()
            del self.leaves[leaf.id]

        self.leaves[leaf.id] = leaf
        if start:
            return leaf.start()
        else:
            return None

    def del_leaf(self, leaf):
        """Удаляет лист с ветви.

        :param leaf: Лист
        :type leaf: Leaf
        """
        leaf.stop()
        if leaf.id in self.leaves:
            del self.leaves[leaf.id]
