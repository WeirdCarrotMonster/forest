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
import zmq
from zmq.eventloop.zmqstream import ZMQStream

from components.common import log_message
from components.logparse import logparse_emperor
from tornado.gen import coroutine


class Vassal(object):

    def __init__(
            self,
            name=None,
            _id=None,
            emperor=None,
            **kwargs
    ):
        self.__name__ = name
        self.__id__ = _id
        self.__emperor__ = emperor
        self.__status__ = "stopped"

    @property
    def id(self):
        return self.__id__

    @property
    def name(self):
        return self.__name__

    @property
    def status(self):
        return self.__status__

    @status.setter
    def status(self, value):
        self.__status__ = value

    def start(self):
        self.__emperor__.start_vassal(self)

    def stop(self):
        self.__emperor__.stop_vassal(self)

    def get_config(self):
        return self.__get_config__()

    def __get_config__(self):
        raise NotImplemented


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
                    if not os.path.exists("/proc/{}".format(emperor_pid)):
                        emperor_pid = 0
                        raise ValueError()

                    log_message("Found running emperor server", component="Emperor")
                except ValueError:
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
                    "--vassal-set", "plugins-dir=%s" % self.binary_dir,
                    "--vassal-set", "buffer-size=65535",
                    "--vassal-set", "heartbeat=10",
                    "--vassal-set", "strict=1"
                ],
                bufsize=1,
                close_fds=True
            )
            code = emperor.wait()

            assert code == 0, "Error starting emperor server"
            log_message("Started emperor server", component="Emperor")

        self.vassal_ports = {}
        self.vassals = {}

        ctx = zmq.Context()
        s = ctx.socket(zmq.PULL)
        s.bind('tcp://127.0.0.1:5123')
        self.stream = ZMQStream(s)
        self.stream.on_recv(self.log_message)

    @property
    def root_dir(self):
        return self.__root_dir__

    @property
    def binary_dir(self):
        return os.path.join(self.root_dir, "bin")

    @property
    def uwsgi_binary(self):
        return os.path.join(self.binary_dir, "uwsgi")

    @property
    def vassal_dir(self):
        return os.path.join(self.root_dir, "vassals")

    @property
    def pidfile(self):
        return os.path.join(self.root_dir, "emperor.pid")

    @property
    def vassal_names(self):
        raw_names = os.listdir(self.vassal_dir)
        return [name[:-4] for name in raw_names]

    def stop(self):
        log_message("Stopping uwsgi emperor", component="Branch")
        subprocess.call([self.uwsgi_binary, "--stop", self.pidfile])
        os.remove(self.pidfile)

        for name in os.listdir(self.vassal_dir):
            os.remove(os.path.join(self.vassal_dir, name))

    def start_vassal(self, vassal):
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
        cfg_path = os.path.join(self.vassal_dir, "{}.ini".format(vassal.id))

        if str(vassal.id) in self.vassals:
            del self.vassals[str(vassal.id)]

        if os.path.exists(cfg_path):
            os.remove(cfg_path)

    def soft_restart_vassal(self, vassal):
        cfg_path = os.path.join(self.vassal_dir, "{}.ini".format(vassal.id))

        if os.path.exists(cfg_path):
            os.utime(cfg_path, None)

    def stats(self, vassal):
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
            if l["id"] == "{}.ini".format(vassal):
                return l

        return {}

    @coroutine
    def log_message(self, message):
        for m in message:
            data, important = logparse_emperor(m.strip())

            if data.get("log_type") == "emperor_vassal_ready":
                vassal_id = data.get("vassal")
                if vassal_id in self.vassals:
                    self.vassals[vassal_id].status = "running"
            elif data.get("log_type") == "emperor_vassal_removed":
                vassal_id = data.get("vassal")
                if vassal_id in self.vassals:
                    self.vassals[vassal_id].status = "stopped"
