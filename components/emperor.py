# -*- coding: utf-8 -*-
"""
Обертка вокруг uwsgi-emperor
"""
from __future__ import print_function, unicode_literals

import os
import signal
import socket
import subprocess
import time

import simplejson as json
import zmq


class Emperor(object):
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
                "--plugin", os.path.join(self.binary_dir, "logzmq"),
                "--emperor", "zmq://tcp://127.0.0.1:%d" % self.port,
                "--emperor-stats-server", "127.0.0.1:%d" % self.stats_port,
                "--master",
                "--logger", "zeromq:tcp://127.0.0.1:%d" % self.logs_port,
                "--emperor-required-heartbeat", "40",
                "--reaper"
            ],
            bufsize=1,
            close_fds=True
        )

        self.vassal_names = {}
        self.vassal_ports = {}

    def stop_emperor(self):
        self.emperor.send_signal(signal.SIGINT)
        self.emperor.wait()

    def start_leaf(self, leaf):
        if leaf.id in self.vassal_names.keys():
            self.stop_leaf(leaf)
        leaf_name = "{}_{}.ini".format(str(leaf.id), str(time.time()).replace(".", ""))
        self.vassal_names[leaf.id] = leaf_name
        leaf.log_port = self.logs_port
        leaf.emperor_dir = self.binary_dir

        self.emperor_socket.send_multipart([
            bytes('touch'),
            bytes(leaf_name),
            bytes(leaf.get_config())
        ])

    def stop_leaf(self, leaf):
        leaf_name = self.vassal_names[leaf.id]
        self.emperor_socket.send_multipart([
            bytes('destroy'),
            bytes(leaf_name)
        ])

        del self.vassal_names[leaf.id]

    def soft_restart_leaf(self, leaf):
        _leaf = self._get_leaves().get(leaf.id, None)
        if not _leaf:
            return

        pid = int(leaf.get("pid"))
        os.kill(pid, signal.SIGHUP)

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
            v.get("id")[:24]: v for v in vassals
        }
