# -*- coding: utf-8 -*-
"""
Модуль реализует сущность ветви, отвечающую за
запуск приложений, обновление репозиториев и логгирование
процессов.
"""
from __future__ import print_function, unicode_literals
from subprocess import CalledProcessError, check_output, STDOUT
from components.leaf import Leaf
from components.common import log_message, LogicError
from components.database import get_default_database
import traceback
import simplejson as json
import datetime
from components.common import CallbackThread as Thread
from components.common import ThreadPool
from threading import Lock
from specie import Specie
from components.emperor import Emperor
from logparse import logparse
from collections import defaultdict
from bson import ObjectId
from decimal import Decimal


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
            "branch.update_state": self.update_state,
            "branch.update_repository": self.update_repository
        }
       
        self.load_components()

        self.emperor = Emperor(self.settings["emperor_dir"])

        self.running = True
        self.logger_thread = Thread(target=self.__log_events)
        self.logger_thread.start()

        self.species = {}
        self.species_lock = Lock()

        self.init_leaves()

    def __get_leaf_by_url(self, host):
        """
        Получает экземпляр листа по связанному с ним адресу

        @param host: Адрес искомого листа
        @type host: str
        @return: Имя найденного листа
        @rtype: str
        """
        for leaf in self.leaves:
            if host in leaf.address:
                return leaf
        return ""

    def get_specie(self, specie_id):
        if specie_id in self.species:
            return self.species[specie_id]

        trunk = get_default_database(self.trunk.settings)

        spc = trunk.species.find_one({"_id": specie_id})

        if spc:
            specie_new = Specie(
                directory=self.settings["species"],
                name=spc.get("name"),
                specie_id=specie_id,
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

    def specie_initialization_finished(self, specie):
        self.species_lock.acquire()

        specie.is_ready = True
        for leaf in self.leaves:
            if leaf.specie == specie and leaf.status[0] == 0:
                self.start_leaf(leaf)

        self.species_lock.release()

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
                
            except json.JSONDecodeError as e:
                data_parsed, important = logparse(data)

            data_parsed["component_name"] = self.trunk.settings["name"]
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
            "branch": self.trunk.settings["name"],
            "active": True
        })

    def get_leaf(self, leaf_name):
        """
        Получает лист по его имени

        @type leaf_name: unicode
        @param leaf_name: Имя искомого листа
        @rtype: Leaf
        @return: Лист по искомому имени
        """
        for leaf in self.leaves:
            if leaf.name == leaf_name:
                return leaf
        return None

    def create_leaf(self, leaf):
        batteries = leaf.get("batteries", {})
        for key, value in batteries.items():
            if key in self.batteries:
                batteries[key]["host"] = self.batteries[key][0][0]
                batteries[key]["port"] = self.batteries[key][0][1]

        trunk = get_default_database(self.trunk.settings)

        new_leaf = Leaf(
            name=leaf["name"],
            leaf_id=leaf.get("_id"),
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
                (leaf.before_start,   []),
                (self.emperor.start_leaf, [leaf])
            ],)
        )
        self.pool.add_thread(t)

    def add_leaf(self, leaf):
        """
        Запускает лист и добавляет его в список запущенных

        @type leaf: Leaf
        @param leaf: Словарь настроек листа
        """
        self.leaves.append(leaf)
        self.species_lock.acquire()
        if leaf.specie.is_ready:
            self.start_leaf(leaf)
        self.species_lock.release()

    def del_leaf(self, leaf):
        self.emperor.stop_leaf(leaf)
        self.leaves.remove(leaf)

    def update_state(self, **kwargs):
        """
        Метод обновления состояния ветви.
        Обновление включает поиск новых листьев, поиск листьев с
        изменившейся конфигурацией, а так же листьев, требующих остановки

        @rtype: dict
        @return: Результат обновления состояния
        """
        # Составляем списки имеющихся листьев и требуемых
        current = [leaf.name for leaf in self.leaves]
        assigned_leaves = {
            i["name"]: i
            for i in self.__get_assigned_leaves()
        }
        assigned = [leaf for leaf in assigned_leaves.keys()]

        # Сравниваем списки листьев
        # Выбираем все листы, которые есть локально, но не
        # указаны в базе и выключаем их
        to_stop  = list(set(current) - set(assigned))
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
                log_message("Leaf {0} changed".format(leaf), component="Branch")
                start_list.append(leaf_shouldb)
                stop_list.append(leaf_running)
                log_restart.append(leaf)

        for leaf in to_start:
            leaf_shouldb = self.create_leaf(assigned_leaves[leaf])
            start_list.append(leaf_shouldb)

        if log_stop:
            log_message("Stopping leaves: {0}".format(log_stop), component="Branch")

        if to_start:
            log_message("Starting leaves: {0}".format(to_start), component="Branch")

        if log_restart:
            log_message("Restarting leaves: {0}".format(log_restart), component="Branch")

        # Выполняем обработку листьев

        for leaf in stop_list:
            self.del_leaf(leaf)

        for leaf in start_list:
            self.add_leaf(leaf)

        return {
            "result": "success"
        }

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

    def update_repository(self, type, **kwargs):
        """
        Метод обновления репозитория.

        @type message: dict
        @param message: Данные репозитория для обновления
        @rtype: dict
        @return: Результат обновления репозитория и логи обновления
        """
        if not type in self.settings["species"].keys():
            return {
                "result": "failure",
                "message": "Unknown repo type"
            }

        repo_path = self.settings["species"][type]["path"]
        repo_type = self.settings["species"][type]["type"]

        try:
            if repo_type == "git":
                cmd = [
                    "git",
                    "--git-dir={0}/.git".format(repo_path),
                    "--work-tree={0}".format(repo_path),
                    "pull"
                ]
                output = check_output(cmd, stderr=STDOUT)
                result = {
                    "result": "success",
                    "message": output
                }
            else:
                raise LogicError("configuration error: unknown repository type")
        except CalledProcessError:
            result = {
                "result": "failure",
                "message": traceback.format_exc()
            }

        to_update = [leaf for leaf in self.leaves if leaf.type == type]

        for leaf in to_update:
            print(leaf.name)
            t = Thread(
                target=leaf.run_tasks, 
                args=([
                    (leaf.before_start,   []),
                    (self.emperor.soft_restart_leaf, [leaf])
                ],)
            )
            self.pool.add_thread(t)

        return result
