# -*- coding: utf-8 -*-
import subprocess
import os
import shutil
import signal
from components.common import get_default_database, log_message


class Air():

    def __init__(self, settings):
        self.settings = settings

        self.update_state(None)

        cmd = [
            "uwsgi",
            "--fastrouter=127.0.0.1:3000",
            "--fastrouter-subscription-server={0}:{1}".format(
                self.settings["host"], str(self.settings["fastrouter"])),
            "--master",
            "--subscriptions-sign-check={0}".format(self.settings["keydir"])
        ]

        self.process = subprocess.Popen(
            cmd,
            bufsize=1,
            close_fds=True,
            stderr=subprocess.PIPE,
            stdout=subprocess.PIPE
        )

    def cleanup(self):
        self.process.send_signal(signal.SIGINT)
        self.process.wait()

    def update_state(self, message):
        trunk = get_default_database(self.settings)

        default_key = os.path.join(self.settings["keydir"], "default.pem")
        for branch in trunk.leaves.find():
            keyfile = os.path.join(
                self.settings["keydir"], branch["address"] + ".pem")
            if not os.path.isfile(keyfile):
                log_message(
                    "Creating key for address: {0}".format(branch["address"]),
                    component="Air")
                shutil.copyfile(default_key, keyfile)

    def status_report(self, message):
        return {
            "result": "success",
            "message": "Working well",
            "role": "air"
        }

    def reload_proxy(self):
        cmd = self.settings["proxy_restart_command"].split()
        subprocess.Popen(cmd, shell=False)
