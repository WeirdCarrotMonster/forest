# -*- coding: utf-8 -*-
"""
Обертка вокруг uwsgi-emperor.

В качестве монитора вассалов используется стандартный glob://, а конфигурационные файлы хранятся в формате ini.
"""

from __future__ import print_function, unicode_literals

import os
import socket
import psutil
import subprocess
from struct import pack, unpack

import simplejson as json
import zmq
from zmq.eventloop.zmqstream import ZMQStream

from forest.components.common import log_message
from forest.components.logparse import logparse_emperor
from tornado.tcpclient import TCPClient
from tornado.gen import coroutine, Return
from tornado.iostream import StreamClosedError


# pylint: disable=W0612,W0613


class Vassal(object):

    def __init__(
            self,
            _id=None,
            emperor=None,
            uwsgi_cron=None,
            uwsgi_mules=None,
            uwsgi_triggers=None,
            **kwargs
    ):
        self.__id__ = _id
        self.__emperor__ = emperor
        self.__status__ = "Stopped"

        self.__uwsgi_cron__ = uwsgi_cron or []
        self.__uwsgi_mules__ = uwsgi_mules or []
        self.__uwsgi_triggers__ = uwsgi_triggers or {}

    @property
    def id(self):
        """Уникальный идентификатор вассала, который может быть использован в имени конфигурационного файла
        :returns: Уникальный идентификатор
        :rtype: str
        """
        return str(self.__id__)

    @property
    def status(self):
        """Текущий статус вассала
        :returns: Статус вассала
        :rtype: str
        """
        return self.__status__

    @status.setter
    def status(self, value):
        """Устанавливает статус вассала и логгирует его
        :param value: Новый статус
        :type value: str
        """
        if value != self.__status__:
            log_message("{} entered '{}' state".format(self.id, value), self.__class__.__name__)
            self.__status__ = value

    @property
    def dict(self):
        """Словарь с базовой конфигурацией вассала, достаточной для его создания
        :returns: Словарь с конфигурацией
        :rtype: dict
        """
        return {
            "cls": self.__class__.__name__,
            "_id": self.__id__,
            "uwsgi_cron": self.__uwsgi_cron__,
            "uwsgi_mules": self.__uwsgi_mules__,
            "uwsgi_triggers": self.__uwsgi_triggers__
        }

    def start(self):
        """Запускает вассала и устанавливает соответствующий статус
        """
        self.status = "Started"
        self.__emperor__.start_vassal(self)

    def stop(self):
        """Останавливает вассала и устанавливает соответствующий статус
        """
        self.status = "Stopped"
        self.__emperor__.stop_vassal(self)

    def get_config(self):
        """Конфигурация вассала для запуска через uwsgi-emperor
        :returns: Конфигарация uwsgi в формате ini
        :rtype: str
        """
        return self.__get_config__()

    def __get_config__(self):
        """Возвращает конфигурацию вассала, используемую при запуске
        Должен быть переопределен в классе-потомке

        :raise NotImplementedError: Метод не переопределен в классе-потомке
        """
        raise NotImplementedError

    def get_cron_config(self):
        """Генерирует конфигурацию uwsgi-cron
        :returns: Строка конфигурации uwsgi
        :rtype: str
        """
        return "\n".join("cron={}".format("".join(_)) for _ in self.__uwsgi_cron__)

    def get_mules_config(self):
        """Генерирует конфигурацию uwsgi-mule
        :returns: Строка конфигурации uwsgi
        :rtype: str
        """
        return "\n".join("mule={}".format(_) for _ in self.__uwsgi_mules__)

    def get_triggers_config(self):
        """Генерирует конфигурацию uwsgi-hooks
        :returns: Строка конфигурации uwsgi
        :rtype: str
        """
        return "\n".join("hook-pre-app=exec:{}".format(_) for _ in self.__uwsgi_triggers__.get("before_start", []))


class Emperor(object):

    def __init__(self, root_dir):
        self.__root_dir__ = root_dir

        if not os.path.exists(self.vassal_dir):
            log_message("Vassal directory does not exist, creating one", component="Emperor")
            os.mkdir(self.vassal_dir)

        emperor_pid = 0

        if os.path.exists(self.pidfile):
            with open(self.pidfile) as pid_file:
                try:
                    emperor_pid = int(pid_file.read())
                    psutil.Process(emperor_pid)

                    log_message("Found running emperor server", component="Emperor")
                except (ValueError, psutil.NoSuchProcess):
                    os.remove(self.pidfile)

        if not emperor_pid:
            emperor = subprocess.Popen(
                [
                    self.uwsgi_binary,
                    "--plugins-dir", self.binary_dir,
                    "--emperor", self.vassal_dir,
                    "--pidfile", self.pidfile,
                    "--logger", "zeromq:tcp://127.0.0.1:5123",
                    "--daemonize", "/dev/null",
                    "--emperor-stats", "127.0.0.1:1777",
                    "--emperor-required-heartbeat", "40",
                    "--emperor-throttle", "10000",
                    "--vassal-set", "plugins-dir=%s" % self.binary_dir
                ],
                bufsize=1,
                close_fds=True
            )
            code = emperor.wait()

            assert code == 0, "Error starting emperor server"
            log_message("Started emperor server", component="Emperor")

        self.vassals = {}

        ctx = zmq.Context()
        s = ctx.socket(zmq.PULL)
        s.bind('tcp://127.0.0.1:5123')
        self.stream = ZMQStream(s)
        self.stream.on_recv(self.log_message)

    @property
    def root_dir(self):
        """Корневая директория uwsgi-emperor
        :returns: Полный путь к корневой директории
        :rtype: str
        """
        return self.__root_dir__

    @property
    def binary_dir(self):
        """Директория с исполняемыми файлами и плагинами uwsgi-emperor
        :returns: Полный путь к директории с исполняемыми файлами
        :rtype: str
        """
        return os.path.join(self.root_dir, "bin")

    @property
    def uwsgi_binary(self):
        """Основной исполняемый файл uwsgi
        :returns: Полный путь к исполняемому файлу uwsgi
        :rtype: str
        """
        return os.path.join(self.binary_dir, "uwsgi")

    @property
    def vassal_dir(self):
        """Директория с вассалами uwsgi
        :returns: Полный путь к директории вассалов
        :rtype: str
        """
        return os.path.join(self.root_dir, "vassals")

    @property
    def pidfile(self):
        """Pid-файл uwsgi-emperor
        :returns: Полный путь к pid-файлу
        :rtype: str
        """
        return os.path.join(self.root_dir, "emperor.pid")

    @property
    def vassal_names(self):
        """Возвращает спиоск имен вассалов, активных в данный момент. Имена передаются без расширения.
        :returns: Список имен активных вассалов
        :rtype: list
        """
        raw_names = os.listdir(self.vassal_dir)
        return [name[:-4] for name in raw_names]

    @coroutine
    def call_vassal_rpc(self, vassal, *args):
        """Вызывает rpc-функцию вассала
        :param vassal: Имя вассала
        :type vassal: str
        :returns: Результат выполнения функции
        :rtype: dict
        """
        stats = self.stats(vassal)
        try:
            assert "pid" in stats

            process = psutil.Process(stats["pid"])
            host, port = process.connections()[0].laddr

            client = yield TCPClient().connect(host, port)
            yield client.write(pack('<BHB', 173, sum(2 + len(arg) for arg in args), 0))

            for arg in args:
                yield client.write(pack('<H', len(arg)) + arg)

            data = yield client.read_bytes(4)
            modifier1, datasize, modifier2 = unpack("<BHB", data)

            data = yield client.read_bytes(datasize)
            raise Return({
                "result": "success",
                "data": data
            })

        except (AssertionError, psutil.NoSuchProcess):
            raise Return({
                "result": "failure",
                "message": "Not running"
            })
        except StreamClosedError:
            raise Return({
                "result": "failure",
                "message": "Call failure"
            })

    def stop(self):
        """Останавливает uwsgi-emperor и очищает директорию вассалов
        """
        log_message("Stopping uwsgi emperor", component="Emperor")
        subprocess.call([self.uwsgi_binary, "--stop", self.pidfile])
        os.remove(self.pidfile)

        for name in os.listdir(self.vassal_dir):
            os.remove(os.path.join(self.vassal_dir, name))

    def start_vassal(self, vassal):
        """Запускает указанного вассала
        :param vassal: Запускаемый вассал
        :type vassal: Vassal
        """
        cfg_path = os.path.join(self.vassal_dir, "{}.ini".format(vassal.id))

        self.vassals[str(vassal.id)] = vassal

        if os.path.exists(cfg_path):
            with open(cfg_path, "r") as cfg:
                data = cfg.read()

            if data == vassal.get_config():
                return

            log_message("Leaf {} have stale configuration, will restart".format(vassal.id))

        with open(cfg_path, "w") as cfg:
            cfg.write(vassal.get_config())

    def stop_vassal(self, vassal):
        """Останавливает указанного вассала
        :param vassal: Останавливаемый вассал
        :type vassal: Vassal
        """
        cfg_path = os.path.join(self.vassal_dir, "{}.ini".format(vassal.id))

        if str(vassal.id) in self.vassals:
            del self.vassals[str(vassal.id)]

        if os.path.exists(cfg_path):
            os.remove(cfg_path)

    def soft_restart_vassal(self, vassal):
        """Выполняет плавный перезапуск вассала
        :param vassal: Перезапускаемый вассал
        :type vassal: Vassal
        """
        cfg_path = os.path.join(self.vassal_dir, "{}.ini".format(vassal.id))

        if os.path.exists(cfg_path):
            os.utime(cfg_path, None)

    def stats(self, vassal):
        """Возвращает статистику по указанному вассалу
        :param vassal: Имя вассала
        :type vassal: str
        :returns: Статистика по вассалу
        :rtype: dict
        """
        for l in self.__stats__()["vassals"]:
            if l["id"] == "{}.ini".format(vassal):
                return l

        return {}

    def __stats__(self):
        """Возвращает внутреннюю статистику uwsgi-emperor
        :returns: Словарь со статистикой
        :rtype: dict
        """
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.connect(("127.0.0.1", 1777))

        data = ""

        while True:
            new_data = s.recv(4096)
            if len(new_data) < 1:
                break
            data += new_data.decode('utf8')

        return json.loads(data)

    @coroutine
    def log_message(self, message):
        """Обрабатывает входящее сообщение uwsgi-emperor
        :param message: Входящее сообщение ZeroMQ
        :type message: list
        """
        for m in (_.strip() for _ in message if _.strip()):
            data = logparse_emperor(m)

            if data.get("log_type") == "emperor_vassal_ready":
                vassal_id = data.get("vassal")
                if vassal_id in self.vassals:
                    self.vassals[vassal_id].status = "Running"
            elif data.get("log_type") == "emperor_vassal_removed":
                vassal_id = data.get("vassal")
                if vassal_id in self.vassals:
                    if self.vassals[vassal_id].status in ("Started", "Failed"):
                        self.vassals[vassal_id].status = "Failed"
                    else:
                        self.vassals[vassal_id].status = "Stopped"
