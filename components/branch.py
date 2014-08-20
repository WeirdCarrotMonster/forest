# -*- coding: utf-8 -*-
"""
Модуль реализует сущность ветви, отвечающую за
запуск приложений, обновление репозиториев и логгирование
процессов.
"""
from __future__ import print_function, unicode_literals

import datetime
from collections import defaultdict
from threading import RLock

import simplejson as json
from bson import ObjectId

from components.common import CallbackThread as Thread
from components.common import log_message, ThreadPool
from components.database import get_default_database
from components.emperor import Emperor
from components.leaf import Leaf
from logparse import logparse
from specie import Specie
from functools import wraps


def synchronous(tlockname):
    """A decorator to place an instance based lock around a method """

    def _synched(func):
        @wraps(func)
        def _synchronizer(self, *args, **kwargs):
            tlock = self.__getattribute__(tlockname)
            tlock.acquire()
            try:
                return func(self, *args, **kwargs)
            finally:
                tlock.release()
        return _synchronizer
    return _synched


class Branch(object):
    """
    Класс ветви, служащий для запуска приложений и логгирования их вывода
    """
    def __init__(self, settings, trunk):
        self.settings = settings
        self.trunk = trunk
        self.leaves = []
        self.pool = ThreadPool(self.settings.get("thread_pool_limit", 0))

        self.functions = {
            "branch.update_state": self.update_state
        }

        self.load_components()

        self.emperor = Emperor(self.settings["emperor_dir"])

        self.running = True
        self.logger_thread = Thread(target=self.__log_events)
        self.logger_thread.start()

        self.species = {}

        # Целый набор локов
        # When in doubt, C4
        self.species_lock = RLock()
        self.leaves_lock = RLock()

        self.init_leaves()

    @synchronous('species_lock')
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
                triggers=spc.get("triggers", {})
            )
            thread = Thread(
                target=specie_new.initialize,
                callback=(self.specie_initialization_finished, [], {"specie": specie_new})
            )
            thread.daemon = True
            thread.start()
            self.species[specie_id] = specie_new
            return self.species[specie_id]

        return None

    @synchronous('leaves_lock')
    def specie_initialization_finished(self, specie):
        specie.is_ready = True
        for leaf in self.leaves:
            if leaf.specie == specie and leaf.status[0] in (0, 3):
                self.start_leaf(leaf)

    def load_components(self):
        self.fastrouters = []
        self.batteries = defaultdict(list)

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

    def __log_events(self):
        add_info = {
            "component_name": self.trunk.settings["name"],
            "component_type": "branch",
            "log_type": "leaf.event"
        }

        trunk = get_default_database(self.trunk.settings)
        while self.running:
            data = self.emperor.get_logs()
            if not data:
                continue
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
            trunk.logs.insert(data_parsed)

    def __get_assigned_leaves(self):
        """
        Метод получения всех листьев, назначенных на данную ветвь.
        Отношение листа к верви определяется соответствием значения поля
        branch листа имени данной ветви

        @rtype: list
        @return: Список всех листьев, назначенных на данную ветвь
        """
        trunk = get_default_database(self.trunk.settings)
        return trunk.leaves.find({
            "branch": self.trunk.settings["id"],
            "active": True
        })

    @synchronous('leaves_lock')
    def get_leaf(self, leaf_id):
        """
        Получает лист по его имени

        @type leaf_name: unicode
        @param leaf_name: Имя искомого листа
        @rtype: Leaf
        @return: Лист по искомому имени
        """
        for leaf in self.leaves:
            if leaf.id == leaf_id:
                return leaf
        return None

    def create_leaf(self, leaf):
        """
        Создает экземпляр листа  по данным из базы

        @type leaf: dict
        @param leaf: Словарь с конфигурацией листа
        @rtype: Leaf
        @return: Созданный по данным базы экземпляр листа
        """
        batteries = leaf.get("batteries", {})
        for key, value in batteries.items():
            if key in self.batteries:
                batteries[key]["host"] = self.batteries[key][0][0]
                batteries[key]["port"] = self.batteries[key][0][1]

        trunk = get_default_database(self.trunk.settings)

        new_leaf = Leaf(
            name=leaf["name"],
            _id=leaf.get("_id"),
            host=self.settings["host"],
            settings=leaf.get("settings", {}),
            fastrouters=self.fastrouters,
            keyfile=self.settings.get("keyfile", None),
            address=leaf.get("address"),
            logger=trunk.logs,
            component=self.trunk.settings["name"],
            batteries=batteries,
            workers=leaf.get("workers", 4),
            threads=leaf.get("threads", False),
            specie=self.get_specie(leaf.get("type"))
        )
        return new_leaf

    def start_leaf(self, leaf):
        t = Thread(
            target=leaf.run_tasks,
            args=([
                (leaf.before_start, []),
                (self.emperor.start_leaf, [leaf])
            ],)
        )
        self.pool.add_thread(t)
        log_message(
            "Starting leaf {}".format(leaf.id),
            component="Branch"
        )

    @synchronous('leaves_lock')
    @synchronous('species_lock')
    def add_leaf(self, leaf):
        """
        Запускает лист и добавляет его в список запущенных

        @type leaf: Leaf
        @param leaf: Словарь настроек листа
        """
        self.leaves.append(leaf)

        if leaf.specie.is_ready:
            self.start_leaf(leaf)
        else:
            log_message(
                "Queued leaf {}".format(leaf.id),
                component="Branch"
            )

    @synchronous('leaves_lock')
    def del_leaf(self, leaf):
        self.emperor.stop_leaf(leaf)
        self.leaves.remove(leaf)

    @synchronous('species_lock')
    def _update_species(self):
        pass

    @synchronous('leaves_lock')
    def _update_leaves(self):
        # Составляем списки имеющихся листьев и требуемых
        current = [leaf.id for leaf in self.leaves]
        assigned_leaves = {
            i["_id"]: i
            for i in self.__get_assigned_leaves()
        }
        assigned = [leaf for leaf in assigned_leaves.keys()]

        # Сравниваем списки листьев
        # Выбираем все листы, которые есть локально, но не
        # указаны в базе и выключаем их
        to_stop = list(set(current) - set(assigned))
        to_start = list(set(assigned) - set(current))
        to_check = list(set(current) & set(assigned))

        log_message("Triggering update", component="Branch")
        log_stop = []
        log_restart = []

        # Формируем списки листьев, с которыми работаем
        stop_list = []
        start_list = []

        for leaf in to_stop:
            stop_list.append(self.get_leaf(leaf))
            log_stop.append(leaf)

        for leaf in to_check:
            leaf_running = self.get_leaf(leaf)
            leaf_shouldb = self.create_leaf(assigned_leaves[leaf])

            if leaf_running != leaf_shouldb:
                log_message(
                    "Leaf {0} changed".format(leaf),
                    component="Branch"
                )
                start_list.append(leaf_shouldb)
                stop_list.append(leaf_running)
                log_restart.append(leaf)

        for leaf in to_start:
            leaf_shouldb = self.create_leaf(assigned_leaves[leaf])
            start_list.append(leaf_shouldb)

        if log_stop:
            log_message(
                "Stopping leaves: {0}".format(log_stop),
                component="Branch"
            )

        if to_start:
            log_message(
                "Starting leaves: {0}".format(to_start),
                component="Branch"
            )

        if log_restart:
            log_message(
                "Restarting leaves: {0}".format(log_restart),
                component="Branch"
            )

        # Выполняем обработку листьев

        for leaf in stop_list:
            self.del_leaf(leaf)

        for leaf in start_list:
            self.add_leaf(leaf)

    def update_state(self, **kwargs):
        """
        Метод обновления состояния ветви.
        В ходе обновления проверяется состояние двух частей ветви:
        1) Репозитории
        2) Листья

        Репозитории обновляются в зависимости от их текущего состояния
        и последней ревизии, указанной в базе.

        Обновление листьев состоит в поиске тех листьев, состояние
        которых на ветви не соответствует состоянию в базе.

        @rtype: dict
        @return: Результат обновления состояния
        """
        self._update_species()
        self._update_leaves()

        return {
            "result": "success"
        }

    @synchronous('leaves_lock')
    def init_leaves(self):
        """
        Метод инициализации листьев при запуске.
        Выбирает назначенные на данную ветвь листья и запускает их
        """
        for leaf in self.__get_assigned_leaves():
            log_message("Found leaf {0} in configuration".format(
                leaf["name"]),
                component="Branch"
            )
            self.add_leaf(self.create_leaf(leaf))

    def cleanup(self):
        """
        Метод выключения листьев при остановке.
        """
        self.emperor.stop_emperor()
        self.running = False
