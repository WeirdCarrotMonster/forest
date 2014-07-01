# -*- coding: utf-8 -*-
"""
Обертка вокруг uwsgi-emperor
"""
from __future__ import print_function, unicode_literals
import os
from subprocess import CalledProcessError, check_output, STDOUT
from components.leaf import Leaf
from components.common import log_message, check_arguments, \
    run_parallel, LogicError, get_default_database, hashfile, get_settings_connection
import traceback
import simplejson as json
import time
import subprocess
import socket
import signal
import zmq
from threading import Thread
import os
import gridfs


class Emperor():
    def __init__(self, binary_dir, port=5121, logs_port=5122, stats_port=5123):
        self.port = port
        self.logs_port = logs_port
        self.stats_port = stats_port
        self.binary_dir = binary_dir

        c = zmq.Context()
        self.emperor_socket = zmq.Socket(c, zmq.PUSH)
        self.emperor_socket.connect('tcp://127.0.0.1:%d' % self.port)
        self.emperor = subprocess.Popen(
            [
                os.path.join(self.binary_dir, "uwsgi"),
                "--plugin", os.path.join(self.binary_dir, "emperor_zeromq"),
                "--emperor", "zmq://tcp://127.0.0.1:%d" % self.port,
                "--emperor-stats-server", "127.0.0.1:%d" % self.stats_port,
                "--master",
                "--logger", "socket:127.0.0.1:%d" % self.logs_port,
                "--emperor-required-heartbeat", "40"
            ],
            bufsize=1,
            close_fds=True
        )
        self.log_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.log_socket.bind(("127.0.0.1", self.logs_port))
        self.log_socket.settimeout(0.5)

        self.vassal_names = {}

    def start_leaf(self, leaf):
        if leaf.name in self.vassal_names.keys():
            self.stop_leaf(leaf)

        leaf_name = "{}_{}.ini".format(leaf.name, str(time.time()).replace(".", ""))
        self.vassal_names[leaf.name] = leaf_name

        self.emperor_socket.send_multipart([
            bytes('touch'),
            bytes(leaf_name),
            bytes(leaf.get_config())
        ])

    def stop_leaf(self, leaf):
        leaf_name = self.vassal_names[leaf.name]
        self.emperor_socket.send_multipart([
            bytes('destroy'),
            bytes(leaf_name)
        ])
        del self.vassal_names[leaf.name]

    def soft_restart_leaf(self, leaf):
        _leaf = self._get_leaves().get(leaf.name, None)
        if not _leaf:
            return

        pid = int(_leaf.get("pid"))
        print(pid)
        os.kill(pid, signal.SIGHUP)

    def get_logs(self):
        try:
            data, addr = self.log_socket.recvfrom(2048)
            return data
        except socket.timeout:
            return None
        except socket.error:
            return None

    def _get_stats(self):
        sock = socket.socket()
        sock.connect(('localhost', self.stats_port))
        data = ""
        while True:
            tmp = sock.recv(256)
            if tmp:
                data += tmp
            else:
                break
        return json.loads(data)

    def _get_leaves(self):
        vassals = self._get_stats().get("vassals", [])
        return {
            v.get("id")[:-4]: v for v in vassals
        }

