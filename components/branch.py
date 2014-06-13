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

        self.emperor_port = 5121
        self.emperor_logs_port = 5122
        c = zmq.Context()
        self.emperor_zmq_socket = zmq.Socket(c, zmq.PUSH)
        self.emperor_zmq_socket.connect('tcp://127.0.0.1:{0}'.format(self.emperor_port))
        self.emperor = subprocess.Popen(
            [
                os.path.join(self.settings["emperor_dir"], "uwsgi"),
                "--plugin", os.path.join(self.settings["emperor_dir"], "emperor_zeromq"),
                "--emperor", "zmq://tcp://127.0.0.1:{0}".format(self.emperor_port),
                "--master",
                "--logger", "socket:127.0.0.1:{0}".format(self.emperor_logs_port),
                "--emperor-required-heartbeat", "40"
            ],
            bufsize=1,
            close_fds=True
        )
        self.log_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.log_socket.bind(("127.0.0.1", self.emperor_logs_port))
        self.log_socket.settimeout(0.5)
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
            try:
                data, addr = self.log_socket.recvfrom(2048)
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
            except socket.timeout:
                pass
            except socket.error:
                pass

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

        trunk = get_default_database(self.settings)

        new_leaf = Leaf(
            name=leaf["name"],
            chdir=repo["path"],
            executable=repo["executable"],
            host=self.settings["host"],
            env=leaf_env,
            settings=leaf.get("settings", {}),
            fastrouters=self.fastrouters,
            keyfile=self.settings.get("keyfile", None),
            address=leaf.get("address") if type(leaf.get("address")) == list else [leaf.get("address")],
            static=repo.get("static"),
            leaf_type=leaf.get("type"),
            emperor=self.emperor_zmq_socket,
            logger=trunk.logs,
            component=self.settings["name"]
        )
        try:
            self.leaves.append(new_leaf)

            t = Thread(
                target=new_leaf.run_tasks, 
                args=([
                    new_leaf.init_database,
                    new_leaf.update_database,
                    new_leaf.start
                ],)
            )
            t.daemon = True
            t.start()
        except Exception:
            raise LogicError("Start failed: {0}".format(traceback.format_exc()))

    def del_leaf(self, leaf):
        leaf.stop()
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
        log_message("Doing following shit:\nto_stop: {0}\nto_start: {1}\nto_check: {2}\ncurrent: {3}\nassigned: {4}\
                    ".format(to_stop, to_start, to_check, current, assigned),
                    component="Branch")

        # Формируем списки листьев, с которыми работаем
        stop_list    = []
        start_list   = []
        restart_list = []

        for leaf in to_stop:
            stop_list.append(self.get_leaf(leaf))

        for leaf in to_check:
            leaf_running = self.get_leaf(leaf)
            leaf_shouldb = assigned_leaves[leaf]

            leaf_shouldb_address = leaf_shouldb.get("address", [])
            if type(leaf_shouldb_address) != list:
                leaf_shouldb_address = [leaf_shouldb_address]

            if leaf_shouldb_address                       != leaf_running.address                   or \
               leaf_shouldb.get("settings", {})           != leaf_running.settings                  or \
               leaf_shouldb.get("env", {}).get("db_pass") != leaf_running.launch_env.get("db_pass") or \
               leaf_shouldb.get("env", {}).get("db_name") != leaf_running.launch_env.get("db_name") or \
               leaf_shouldb.get("env", {}).get("db_user") != leaf_running.launch_env.get("db_user"):
                # Прости меня, Один, за такие проверки
                log_message("Leaf {0} changed".format(leaf),
                    component="Branch"
                )
                stop_list.append(leaf_running)
                start_list.append(leaf_shouldb)

        for leaf in to_start:
            start_list.append(assigned_leaves[leaf])

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
            self.add_leaf(leaf)

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

        trunk = get_default_database(self.settings)
        con = get_settings_connection(self.settings)
        specie = trunk.species.find_one({"name": repo_name})
        fs = gridfs.GridFS(con.files)

        
        if specie and specie.get("static"):
            static_dir = specie.get("static")
            static_path = os.path.join(repo_path, static_dir)

            current_files = set()

            # Собираем множество всех файлов, существующих в папке со статикой после обновления
            for path, subdirs, files in os.walk(static_path):        
                for name in files:                            
                    filename = os.path.join(path, name)[len(static_path):]
                    if filename.startswith("/"):
                        filename = filename[1:]
                    current_files.add(filename)

            processed = set()

            for grid_file in fs.find({"species": specie["name"]}):
                # Пачка вариантов развития событий:
                if not grid_file.filename in current_files:
                    # 1: Файла больше нет
                    log_message("File {0} no longer exists in static".format(
                        grid_file.filename),
                        component="Branch"
                    )
                    fs.delete(grid_file._id)
                else:
                    # 2: Файл есть - сравниваем его с локальной копией
                    with open(os.path.join(static_path, grid_file.filename), 'r') as local_file:
                        if hashfile(local_file) != grid_file.md5:
                            # Файл изменился - заливаем его заново
                            log_message("File {0} changed - uploading".format(
                                grid_file.filename),
                                component="Branch"
                            )
                            fs.delete(grid_file._id)
                            fs.put(local_file, filename=grid_file.filename, species=specie["name"])
                processed.add(grid_file.filename)

            for local_file_name in current_files:
                if not local_file_name in processed:
                    log_message("New file {0}".format(local_file_name), component="Branch")
                    with open(os.path.join(static_path, local_file_name), 'r') as local_file:

                        fs.put(
                            local_file,
                            filename=local_file_name,
                            species=specie["name"],
                            content_type=mimetypes.guess_type(local_file_name)[0]
                        )

        to_update = [leaf for leaf in self.leaves if leaf.type == repo_type]

        trunk = get_default_database(self.settings)
        for leaf in to_update:
            t = Thread(
                target=leaf.run_tasks, 
                args=([
                    leaf.stop,
                    leaf.init_database,
                    leaf.update_database,
                    leaf.start
                ],)
            )
            t.daemon = True
            t.start()

        return result
