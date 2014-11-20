# -*- coding: utf-8 -*-
import os
import shutil
import signal
import subprocess

from tornado import gen

from components.common import log_message


try:
    from subprocess import DEVNULL  # py3k
except ImportError:
    import os
    DEVNULL = open(os.devnull, 'wb')


class Air():
    def __init__(self, settings, trunk, port=3000, logs_port=2999):
        self.settings = settings
        self.trunk = trunk
        self.port = port
        self.logs_port = logs_port

        cmd_fastrouter = [
            os.path.join(self.trunk.forest_root, "bin/uwsgi"),
            "--fastrouter=127.0.0.1:%d" % self.port,
            "--fastrouter-subscription-server={0}:{1}".format(
                self.settings["host"], str(self.settings["fastrouter"])),
            "--master",
            "--processes=4",
            "--subscriptions-sign-check=SHA1:{0}".format(os.path.join(self.trunk.forest_root, "keys")),
            # "--logger", "socket:127.0.0.1:%d" % self.logs_port
        ]

        self.fastrouter = subprocess.Popen(
            cmd_fastrouter,
            stdout=DEVNULL,
            stderr=DEVNULL
        )
        self.last_update = None

    @gen.coroutine
    def periodic_event(self):
        query = {"batteries": {'$exists': True}}
        if self.last_update:
            query["modified"] = {"$gt": self.last_update}

        cursor = self.trunk.async_db.leaves.find(query)

        default_key = os.path.join(self.trunk.forest_root, "keys/default.pem")

        while (yield cursor.fetch_next):
            leaf = cursor.next_object()

            if not self.last_update or self.last_update < leaf.get("modified"):
                self.last_update = leaf.get("modified")

            for add in leaf.get("address", []):
                key_file = os.path.join(self.trunk.forest_root, "keys/{}.pem".format(add))

                if not os.path.isfile(key_file):
                    log_message("Creating key for address: {0}".format(add), component="Air")
                    shutil.copyfile(default_key, key_file)

    def cleanup(self):
        self.fastrouter.send_signal(signal.SIGINT)
        self.fastrouter.wait()