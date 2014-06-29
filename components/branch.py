# -*- coding: utf-8 -*-
"""
Модуль реализует сущность ветви, отвечающую за
запуск приложений, обновление репозиториев и логгирование
процессов.
"""
from __future__ import print_function, unicode_literals
import os
from subprocess import CalledProcessError, check_output, STDOUT
from components.leaf import Leaf
from components.common import log_message, check_arguments, \
    run_parallel, LogicError, get_default_database, hashfile, get_settings_connection
import traceback
import simplejson as json
import psutil
import datetime
import subprocess
import socket
import signal
import zmq
from threading import Thread
import os
import gridfs
import mimetypes
from components.emperor import Emperor


class Branch(object):
    """
    Класс ветви, служащий для запуска приложений и логгирования их вывода
    """
    def __init__(self, settings):
        self.settings = settings
        self.leaves = []

        trunk = get_default_database(self.settings)
        self.fastrouters = []
        self.roots = []
        components = trunk.components
        for component in components.find({"roles.air": {"$exists": True}}):
            host = component["host"]
            port = component["roles"]["air"]["fastrouter"]
            self.fastrouters.append("{0}:{1}".format(host, port))

        for component in components.find({"roles.roots": {"$exists": True}}):
            self.roots.append(
                (component["roles"]["roots"]["mysql_host"],
                 component["roles"]["roots"]["mysql_port"])
            )

        self.emperor = Emperor(self.settings["emperor_dir"])

        self.running = True
        self.logger_thread = Thread(target=self.__log_events)
        self.logger_thread.start()
        self.init_leaves()

    def __get_leaf_by_url(self, host):
        for leaf in self.leaves:
            if host in leaf.address:
                return leaf
        return ""

    def __log_events(self):
        add_info = {
            "component_name": self.settings["name"],
            "component_type": "branch",
            "log_type": "leaf.event"
        }

        trunk = get_default_database(self.settings)
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
                data_parsed["log_source"] = self.__get_leaf_by_url(data_parsed["host"]).name
                data_parsed["specie"] = self.__get_leaf_by_url(data_parsed["host"]).type
                data_parsed["added"] = datetime.datetime.now()
                trunk.logs.insert(data_parsed)
            except Exception as e:
                trunk.logs.insert({
                    "component_name": self.settings["name"],
                    "component_type": "branch",
                    "log_type": "branch.event",
                    "content": data,
                    "added": datetime.datetime.now()
                })

    def __get_assigned_leaves(self):
        """
        Метод получения всех листьев, назначенных на данную ветвь.
        Отношение листа к верви определяется соответствием значения поля
        branch листа имени данной ветви

        @rtype: list
        @return: Список всех листьев, назначенных на данную ветвь
        """
        trunk = get_default_database(self.settings)
        return trunk.leaves.find({
            "branch": self.settings["name"],
            "active": True
        })

    def save_leaf_logs(self):
        """
        Метод логгирования событий листьев.
        Читает накопившиеся события из потока чтения событий
        и сохраняет их в коллекцию logs MongoDB
        """
        trunk = get_default_database(self.settings)

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
        repo = self.settings["species"][leaf.get("type")]

        leaf_env = leaf.get("env", {})
        leaf_env["db_host"] = self.roots[0][0]
        leaf_env["db_port"] = self.roots[0][1]

        trunk = get_default_database(self.settings)

        new_leaf = Leaf(
            name=leaf["name"],
            path=repo["path"],
            executable=repo["executable"],
            host=self.settings["host"],
            env=leaf_env,
            settings=leaf.get("settings", {}),
            fastrouters=self.fastrouters,
            keyfile=self.settings.get("keyfile", None),
            address=leaf.get("address") if type(leaf.get("address")) == list else [leaf.get("address")],
            static=repo.get("static"),
            leaf_type=leaf.get("type"),
            logger=trunk.logs,
            component=self.settings["name"]
        )
        return new_leaf

    def add_leaf(self, leaf):
        """
        Запускает лист и добавляет его в список запущенных

        @type leaf: dict
        @param leaf: Словарь настроек листа
        """
        self.leaves.append(leaf)

        t = Thread(
            target=leaf.run_tasks,
            args=([
                (leaf.init_database,   []),
                (leaf.update_database, []),
                (self.emperor.start_leaf, [leaf])
            ],)
        )
        t.daemon = True
        t.start()

    def del_leaf(self, leaf):
        self.emperor.stop_leaf(leaf)
        self.leaves.remove(leaf)

    def update_state(self, *args, **kwargs):
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
        self.emperor.send_signal(signal.SIGINT)
        self.emperor.wait()
        self.running = False

    def update_repo(self, message):
        """
        Метод обновления репозитория.

        @type message: dict
        @param message: Данные репозитория для обновления
        @rtype: dict
        @return: Результат обновления репозитория и логи обновления
        """
        check_arguments(message, ["type"])
        repo_name = message["type"]

        if not repo_name in self.settings["species"].keys():
            return {
                "result": "failure",
                "message": "Unknown repo type"
            }

        repo_path = self.settings["species"][repo_name]["path"]
        repo_type = self.settings["species"][repo_name]["type"]

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

        to_update = [leaf for leaf in self.leaves if leaf.type == repo_name]

        trunk = get_default_database(self.settings)
        for leaf in to_update:
            print(leaf.name)
            t = Thread(
                target=leaf.run_tasks, 
                args=([
                    (leaf.init_database,   []),
                    (leaf.update_database, []),
                    (self.emperor.soft_restart_leaf, [leaf])
                ],)
            )
            t.daemon = True
            t.start()

        return result
