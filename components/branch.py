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
    run_parallel, LogicError, get_default_database
import traceback
import psutil
import datetime


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
        self.init_leaves()

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

        for leaf in self.leaves:
            logs = leaf.update_logs_req_count()
            for log in logs:
                trunk.logs.insert({
                    "component_name": self.settings["name"],
                    "component_type": "branch",
                    "log_source": leaf.name,
                    "log_type": "leaf.event",
                    "content": log,
                    "added": datetime.datetime.now()
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

    def add_leaf(self, leaf):
        """
        Запускает лист и добавляет его в список запущенных

        @type leaf: dict
        @param leaf: Словарь настроек листа
        """
        # TODO: переписывать адрес MySQL-сервера, выбирая его из базы
        repo = self.settings["species"][leaf.get("type")]

        leaf_env = leaf.get("env", {})
        leaf_env["db_host"] = self.roots[0][0]
        leaf_env["db_port"] = self.roots[0][1]

        new_leaf = Leaf(
            name=leaf["name"],
            chdir=repo["path"],
            executable=repo["executable"],
            host=self.settings["host"],
            env=leaf_env,
            settings=leaf.get("settings", {}),
            fastrouters=self.fastrouters,
            keyfile=self.settings.get("keyfile", None),
            address=leaf.get("address"),
            static=repo["static"],
            leaf_type=leaf.get("type")
        )
        try:
            new_leaf.start()
            self.leaves.append(new_leaf)
            db_logs = new_leaf.init_database()
            trunk = get_default_database(self.settings)
            for log in db_logs:
                trunk.logs.insert({
                    "component_name": self.settings["name"],
                    "component_type": "branch",
                    "log_source": new_leaf.name,
                    "log_type": "leaf.initdb",
                    "content": log,
                    "added": datetime.datetime.now()
                })
        except Exception:
            raise LogicError("Start failed: {0}".format(traceback.format_exc()))

    def status_report(self, **kwargs):
        """
        Метод генерации отчета о состоянии сервера
        Отчет включает данные о нагрузке на 15, 5 и 1 минуту,
        свободной памяти и аптайме сервера

        @rtype: dict
        @return: Данные о состоянии сервера
        """
        # Память
        mem = psutil.virtual_memory()
        swap = psutil.swap_memory()
        # Нагрузка
        load_1, load_5, load_15 = os.getloadavg()
        # Аптайм
        try:
            f = open("/proc/uptime")
            contents = f.read().split()
            f.close()

            total_seconds = float(contents[0])

            minute = 60
            hour = minute * 60
            day = hour * 24

            days = int(total_seconds / day)
            hours = int((total_seconds % day) / hour)
            minutes = int((total_seconds % hour) / minute)
            seconds = int(total_seconds % minute)
        except:
            days = 0
            hours = 0
            minutes = 0
            seconds = 0

        measurements = {
            "mem_total": mem.total / (1024 * 1024),
            "mem_used": (mem.used - mem.buffers - mem.cached) / (1024 * 1024),
            "mem_cached": (mem.buffers + mem.cached) / (1024 * 1024),
            "mem_free": mem.free / (1024 * 1024),
            "swap_total": swap.total / (1024 * 1024),
            "swap_used": swap.used / (1024 * 1024),
            "swap_free": swap.free / (1024 * 1024),
            "load_1": load_1,
            "load_5": load_5,
            "load_15": load_15,
            "uptime_days": days,
            "uptime_hours": hours,
            "uptime_minutes": minutes,
            "uptime_seconds": seconds
        }
        return {
            "result": "success",
            "message": "Working well",
            "role": "branch",
            "measurements": measurements
        }

    def update_state(self, *args, **kwargs):
        """
        Метод обновления состояния ветви.
        Обновление включает поиск новых листьев, поиск листьев с
        изменившейся конфигурацией, а так же листьев, требующих остановки

        @rtype: dict
        @return: Результат обновления состояния
        """
        # Составляем списки имеющихся листьев и требуемых
        current_leaves = [leaf.name for leaf in self.leaves]
        db_leaves = [leaf for leaf in self.__get_assigned_leaves()]
        db_leaves_names = [leaf["name"] for leaf in db_leaves]

        # Сравниваем списки листьев
        # Выбираем все листы, которые есть локально, но не
        # указаны в базе и выключаем их
        to_remove = list(set(current_leaves) - set(db_leaves_names))
        to_update = list(set(current_leaves) & set(db_leaves_names))
        to_append = list(set(db_leaves_names) - set(current_leaves))

        log_message("Triggering update", component="Branch")
        log_message("Doing following shit:\n\
                     to_remove: {0}\n\
                     to_update: {1}\n\
                     to_append: {2}\n\
                     current_leaves: {3}\
                    ".format(to_remove, to_update, to_append, current_leaves),
                    component="Branch")

        for leaf in self.leaves:
            if leaf.name in to_remove:
                leaf.stop()
                self.leaves.remove(leaf)

        for leaf in db_leaves:
            if leaf["name"] in to_update:
                leaf_running = self.get_leaf(leaf["name"])
                if leaf.get("settings", {}) != leaf_running.settings or \
                   leaf["env"] != leaf_running.launch_env or \
                   leaf["address"] != leaf_running.address:
                    log_message("Leaf {0} configuration changed, reloading\
                                ".format(leaf["name"]), component="Branch")
                    leaf_running.settings = leaf["settings"]
                    leaf_running.env = leaf["env"]
                    leaf_running.address = leaf["address"]
                    leaf_running.restart()
            elif leaf["name"] in to_append:
                log_message("Adding leaf {0}".format(leaf["name"]),
                            component="Branch")
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
            self.add_leaf(leaf)

    def cleanup(self):
        """
        Метод выключения листьев при остановке.
        """
        log_message("Shutting down leaves...", component="Branch")
        run_parallel([leaf.stop for leaf in self.leaves])

    def known_leaves(self, message):
        """
        Метод, возвращающий состояние работающих листьев.

        @rtype: dict
        @return: Данные о функционирующих листьях
        """
        known_leaves = []
        for leaf in self.leaves:
            known_leaves.append({
                "name": leaf.name,
                "env": leaf.launch_env,
                "settings": leaf.settings,
                "mem": leaf.mem_usage(),
                "req": leaf.req_per_second()
            })
        return {
            "result": "success",
            "leaves": known_leaves
        }

    def restart_leaf(self, message):
        """
        Метод перезапуска листа.
        Выполняет грубый перезапуск листа, останавливая его и запуская снова

        @type message: dict
        @param message: Данные листа для перезапуска
        @rtype: dict
        @return: Результат перезапуска
        """
        leaf_data = check_arguments(message, ["name"])
        leaf = self.get_leaf(leaf_data["name"])
        if leaf:
            leaf.restart()
        else:
            raise LogicError("Leaf with name {0} not found".format(
                leaf_data["name"]))

        log_message("Restarting leaf '{0}'".format(
            leaf_data["name"]), component="Branch")

        return {
            "result": "success",
            "message": "restarted leaf {0}".format(leaf_data["name"])
        }

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

        to_update = [leaf for leaf in self.leaves if leaf.type == repo_type]

        trunk = get_default_database(self.settings)
        for leaf in to_update:
            logs = leaf.update_database()
            for log in logs:
                trunk.logs.insert({
                    "component_name": self.settings["name"],
                    "component_type": "branch",
                    "log_source": leaf.name,
                    "log_type": "leaf.updatedb",
                    "content": log,
                    "added": datetime.datetime.now()
                })

        for leaf in to_update:
            leaf.graceful_restart()

        return result
