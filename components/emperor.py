# -*- coding: utf-8 -*-
"""
Обертка вокруг uwsgi-emperor.

В качестве монитора вассалов используется стандартный glob://, а конфигурационные файлы хранятся в формате ini.
"""
from __future__ import print_function, unicode_literals

import os
import socket
import subprocess

import simplejson as json

from components.common import log_message


class Emperor(object):

    def __init__(self, root_dir, leaves_host, logs_port=5122):
        self.__leaves_host = leaves_host
        self.__logs_port = logs_port
        self.__forest_root = root_dir

        self.__binary_dir = os.path.join(root_dir, "bin")
        self.__uwsgi_binary = os.path.join(self.__binary_dir, "uwsgi")
        self.__vassal_dir = os.path.join(root_dir, "vassals")
        self.__pid_file = os.path.join(root_dir, "emperor.pid")

        if not os.path.exists(self.__vassal_dir):
            log_message("Vassal directory does not exist, creating one", component="Branch")
            os.mkdir(self.__vassal_dir)

        emperor_pid = 0

        if os.path.exists(self.__pid_file):
            with open(self.__pid_file) as pid_file:
                try:
                    emperor_pid = int(pid_file.read())
                    if not os.path.exists("/proc/{}".format(emperor_pid)):
                        emperor_pid = 0
                        raise ValueError()

                    log_message("Found running emperor server", component="Branch")
                except ValueError:
                    os.remove(self.__pid_file)

        if not emperor_pid:
            emperor = subprocess.Popen(
                [
                    self.__uwsgi_binary,
                    "--plugins-dir", self.__binary_dir,
                    "--emperor", "%s" % self.__vassal_dir,
                    "--pidfile", self.__pid_file,
                    "--daemonize", "/dev/null",
                    "--logger", "zeromq:tcp://127.0.0.1:%d" % self.__logs_port,
                    "--emperor-stats", "127.0.0.1:1777",
                    "--emperor-required-heartbeat", "40",
                    "--emperor-throttle", "10000",  # TODO: Настраивать? Не уверен, нужно ли
                    "--vassal-set", "socket=%s:0" % self.__leaves_host,
                    "--vassal-set", "plugins-dir=%s" % self.__binary_dir,
                    "--vassal-set", "req-logger=zeromq:tcp://127.0.0.1:%d" % self.__logs_port,
                    "--vassal-set", "buffer-size=65535",
                    "--vassal-set", "heartbeat=10",
                    "--vassal-set", "master=1",
                    "--vassal-set", "strict=1"
                ],
                bufsize=1,
                close_fds=True
            )
            code = emperor.wait()

            assert code == 0, "Error starting emperor server"
            log_message("Started emperor server", component="Branch")

        self.vassal_ports = {}

    @property
    def vassal_names(self):
        """
        Получает список имен вассалов, запущенных в данный момент на emperor-сервере.
        Список генерируется получанием имен конфигурационных файлов, размещенных в директории, которую мониторит
        emperor. От имени файла отбрасывается расширение, оставшаяся часть (в случае, если файл был создан через
        Forest), является строковым представлением ObjectId.

        :return: Список имен запущенных вассалов
        :rtype: list
        """
        raw_names = os.listdir(self.__vassal_dir)
        return [name[:-4] for name in raw_names]

    def stop_emperor(self):
        """
        Выполняет остановку emperor-сервера, убивая процесс с pid, указанным в `self.__pid_file`, а так же очищает
        директорию вассалов для.

        """
        log_message("Stopping uwsgi emperor", component="Branch")
        subprocess.call([self.__uwsgi_binary, "--stop", self.__pid_file])
        os.remove(self.__pid_file)

        for name in os.listdir(self.__vassal_dir):
            os.remove(os.path.join(self.__vassal_dir, name))

    def start_leaf(self, leaf):
        """
        Запускает лист через uwsgi-emperor в качестве вассала

        При запуске листа его конфигурационный файл размещается в директории, сохраненной в `self.__vassal_dir`.

        :param leaf: Запускаемый лист
        :type leaf: Leaf
        """
        cfg_path = os.path.join(self.__vassal_dir, "{}.ini".format(leaf.id))
        if os.path.exists(cfg_path):
            with open(cfg_path, "r") as cfg:
                data = cfg.read()

            if data == leaf.get_config():
                return

            log_message("Leaf {} have stale configuration, will restart".format(leaf.name))

        with open(cfg_path, "w") as cfg:
            cfg.write(leaf.get_config())

    def stop_leaf(self, leaf):
        """
        Останавливает лист через uwsgi emperor

        :param leaf: Останавливаемый лист
        :type leaf: Leaf
        """
        cfg_path = os.path.join(self.__vassal_dir, "{}.ini".format(leaf.id))

        if os.path.exists(cfg_path):
            os.remove(cfg_path)

    def soft_restart_leaf(self, leaf):
        """
        Выполняет плавный перезапуск листа.

        TODO: оттестировать

        :param leaf: Перезапускаемый лист
        :type leaf: Leaf
        """
        cfg_path = os.path.join(self.__vassal_dir, "{}.ini".format(leaf.id))

        if os.path.exists(cfg_path):
            os.utime(cfg_path, None)

    def stats(self, leaf):
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.connect(("127.0.0.1", 1777))

        data = ""

        while True:
            new_data = s.recv(4096)
            if len(new_data) < 1:
                break
            data += new_data.decode('utf8')

        data = json.loads(data)

        for l in data["vassals"]:
            if l["id"] == "{}.ini".format(leaf):
                return l

        return {}
