# -*- coding: utf-8 -*-
import os
import shutil
import signal
import socket
import subprocess
from threading import Thread

from components.common import log_message
from components.database import get_default_database
from logparse import logparse


class Air():
    def __init__(self, settings, trunk, port=3000, logs_port=2999):
        self.settings = settings
        self.trunk = trunk
        self.port = port
        self.logs_port = logs_port

        cmd_fastrouter = [
            os.path.join(self.settings["emperor_dir"], "uwsgi"),
            "--fastrouter=127.0.0.1:%d" % self.port,
            "--fastrouter-subscription-server={0}:{1}".format(
                self.settings["host"], str(self.settings["fastrouter"])),
            "--master",
            "--subscriptions-sign-check=SHA1:{0}".format(self.settings["keydir"]),
            # "--logger", "socket:127.0.0.1:%d" % self.logs_port
        ]

        self.fastrouter = subprocess.Popen(
            cmd_fastrouter,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE
        )
        self.last_update = None

    def periodic_event(self):
        trunk = get_default_database(self.trunk.settings, async=True)
        query = {"batteries": {'$exists': True}}
        if self.last_update:
            query["modified"] = {"$gt": self.last_update}

        cursor = trunk.leaves.find(query)
        cursor.each(callback=self._found_leaf)

    def _found_leaf(self, result, error):
        if not result:
            return

        if not self.last_update or self.last_update < result.get("modified"):
            self.last_update = result.get("modified")

        default_key = os.path.join(self.settings["keydir"], "default.pem")
        for add in result.get("address", []):
            keyfile = os.path.join(
                self.settings["keydir"], add + ".pem")
            if not os.path.isfile(keyfile):
                log_message(
                    "Creating key for address: {0}".format(add),
                    component="Air")
                shutil.copyfile(default_key, keyfile)

    def cleanup(self):
        self.fastrouter.send_signal(signal.SIGINT)
        self.fastrouter.wait()