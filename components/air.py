# -*- coding: utf-8 -*-
import subprocess
import os
import shutil
import signal
import socket
from components.common import get_default_database, log_message
from threading import Thread
from logparse import logparse
import re


class Air():
    def __init__(self, settings, trunk, port=3000, logs_port=2999):
        self.settings = settings
        self.trunk = trunk
        self.port = port
        self.logs_port = logs_port

        self.functions = {
            "air.update_state": self.update_state
        }

        self.update_state()

        cmd_fastrouter = [
            os.path.join(self.settings["emperor_dir"], "uwsgi"),
            "--fastrouter=127.0.0.1:%d" % self.port,
            "--fastrouter-subscription-server={0}:{1}".format(
                self.settings["host"], str(self.settings["fastrouter"])),
            "--master",
            "--subscriptions-sign-check=SHA1:{0}".format(self.settings["keydir"]),
            "--logger", "socket:127.0.0.1:%d" % self.logs_port
        ]

        self.fastrouter = subprocess.Popen(cmd_fastrouter)

        self.log_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.log_socket.bind(("127.0.0.1", self.logs_port))
        self.log_socket.settimeout(0.5)

        self.logger_thread = Thread(target=self.__logger)
        self.logger_thread.daemon = True
        self.logger_thread.start()

    def __logger(self):
        while True:
            try:
                data, addr = self.log_socket.recvfrom(2048)

                # ==============
                # Проверяем соответствие регуляркам
                data_parsed, important = logparse(data)
                # print(data_parsed)

            except socket.timeout:
                pass
            except socket.error:
                pass


    def cleanup(self):
        self.fastrouter.send_signal(signal.SIGINT)
        self.fastrouter.wait()

    def update_state(self, **kwargs):
        trunk = get_default_database(self.trunk.settings)

        default_key = os.path.join(self.settings["keydir"], "default.pem")
        for branch in trunk.leaves.find():
            address = branch["address"] if type(branch["address"]) == list else [branch["address"]]
            for add in address:
                keyfile = os.path.join(
                    self.settings["keydir"], add + ".pem")
                if not os.path.isfile(keyfile):
                    log_message(
                        "Creating key for address: {0}".format(add),
                        component="Air")
                    shutil.copyfile(default_key, keyfile)

        return {
            "result": "success"
        }

    def status_report(self, message):
        return {
            "result": "success",
            "message": "Working well",
            "role": "air"
        }
