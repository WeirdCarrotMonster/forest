# -*- coding: utf-8 -*-
import subprocess
import tornado.web
import tornado.httpclient
import os
import shutil
import signal
from components.common import get_connection, log_message


class Air(tornado.web.Application):

    def __init__(self, settings_dict, **settings):
        super(Air, self).__init__(**settings)
        self.settings = settings_dict

        self.functions = {
            "update_state": self.update_state,
            "status_report": self.status_report
        }
        self.update_state(None)

        cmd = [
            "uwsgi",
            "--fastrouter=127.0.0.1:3000",
            "--fastrouter-subscription-server={0}:{1}".format(
                self.settings["ip"], str(self.settings["fastrouter"])),
            "--master"
        ]

        self.process = subprocess.Popen(
            cmd,
            bufsize=1,
            close_fds=True
        )

    def cleanup(self):
        self.process.send_signal(signal.SIGINT)
        self.process.wait()

    def update_state(self, message):
        client = get_connection(
            self.settings["mongo_host"],
            self.settings["mongo_port"],
            "admin",
            "password"
        )

        default_key = os.path.join(self.settings["keydir"], "default.pem")
        for branch in client.trunk.leaves.find():
            keyfile = os.path.join(
                self.settings["keydir"], branch["address"] + ".pem")
            if not os.path.isfile(keyfile):
                log_message(
                    "Creating key for address: {0}".format(branch["address"]),
                    component="Air")
                shutil.copyfile(default_key, keyfile)

    def process_message(self, message):
        function = message.get('function', None)

        if not function in self.functions:
            return {
                "result": "failure",
                "message": "No function or unknown one called"
            }

        return self.functions[function](message)

    def status_report(self, message):
        return {
            "result": "success",
            "message": "Working well",
            "role": "air"
        }

    def reload_proxy(self):
        cmd = self.settings["proxy_restart_command"].split()
        subprocess.Popen(cmd, shell=False)
