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
from tornado.ioloop import PeriodicCallback
from tornado.iostream import StreamClosedError


# pylint: disable=W0612,W0613


class Vassal(object):

    def __init__(
            self,
            _id=None,
            name=None,
            emperor=None,
            uwsgi_cron=None,
            uwsgi_mules=None,
            uwsgi_triggers=None,
            **kwargs
    ):
        self.__id__ = _id
        self.__name__ = name
        self.__emperor__ = emperor
        self.__status__ = "stopped"

        self.__uwsgi_cron__ = uwsgi_cron or []
        self.__uwsgi_mules__ = uwsgi_mules or []
        self.__uwsgi_triggers__ = uwsgi_triggers or {}

    @property
    def id(self):
        return self.__id__

    @property
    def name(self):
        return self.__name__

    @property
    def status(self):
        return self.__status__

    @property
    def dict(self):
        return {
            "cls": self.__class__.__name__,
            "_id": self.__id__,
            "name": self.__name__,
            "uwsgi_cron": self.__uwsgi_cron__,
            "uwsgi_mules": self.__uwsgi_mules__,
            "uwsgi_triggers": self.__uwsgi_triggers__
        }

    @status.setter
    def status(self, value):
        component = self.__class__.__name__
        log_message("{} entered '{}' state".format(self.id, value), component=component)
        self.__status__ = value

    def start(self):
        self.status = "Started"
        self.__emperor__.start_vassal(self)

    def stop(self):
        self.status = "Stopped"
        self.__emperor__.stop_vassal(self)

    def get_config(self):
        return self.__get_config__()

    def __get_config__(self):
        raise NotImplementedError

    def get_mules_config(self):
        return "\n{}\n".format("\n".join("mule={}".format(mule) for mule in self.__uwsgi_mules__))

    def get_cron_config(self):
        return "\n{}\n".format("\n".join("cron={}".format(" ".join(str(c) for c in _)) for _ in self.__uwsgi_cron__))


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

        self.__scan_callback__ = PeriodicCallback(self.__read_vassals_status__, 5000)
        self.__scan_callback__.start()

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

    @coroutine
    def __read_vassals_status__(self):
        for vassal in self.__stats__()["vassals"]:
            if vassal["id"][0:-4] in self.vassals:
                if vassal["ready"] == 1 and self.vassals[vassal["id"][0:-4]].status != "Running":
                    self.vassals[vassal["id"][0:-4]].status = "Running"

    @coroutine
    def call_vassal_rpc(self, vassal, *args):
        stats = self.stats(vassal)
        try:
            assert "pid" in stats

            process = psutil.Process(stats["pid"])
            host, port = process.connections()[0].laddr

            client = yield TCPClient().connect(host, port)
            yield client.write(pack('<BHB', 173, sum(2 + len(arg) for arg in args), 0))

            for arg in args:
                yield client.write(pack('<H', len(arg)) + arg)

            print(1)
            data = yield client.read_bytes(4)
            print(1)
            modifier1, datasize, modifier2 = unpack("<BHB", data)

            data = yield client.read_bytes(datasize)
            print(3)
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
        log_message("Stopping uwsgi emperor", component="Emperor")
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
        for l in self.__stats__()["vassals"]:
            if l["id"] == "{}.ini".format(vassal):
                return l

        return {}

    def __stats__(self):
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
        for m in message:
            data, important = logparse_emperor(m.strip())

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
