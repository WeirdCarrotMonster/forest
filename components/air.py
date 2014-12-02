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
        self.__uwsgi_binary = os.path.join(self.trunk.forest_root, "bin/uwsgi")
        self.__pid_file = os.path.join(self.trunk.forest_root, "fastrouter.pid")

        fastrouter_pid = 0

        if os.path.exists(self.__pid_file):
            with open(self.__pid_file) as pid_file:
                try:
                    fastrouter_pid = int(pid_file.read())
                    if not os.path.exists("/proc/{}".format(fastrouter_pid)):
                        raise ValueError()

                    log_message("Found running fastrouter", component="Air")
                except ValueError:
                    os.remove(self.__pid_file)

        if not fastrouter_pid:
            fastrouter = subprocess.Popen(
                [
                    self.__uwsgi_binary,
                    "--fastrouter=127.0.0.1:%d" % self.port,
                    "--pidfile=%s" % self.__pid_file,
                    "--daemonize=/dev/null",
                    "--fastrouter-subscription-server={0}:{1}".format(
                        self.settings["host"], str(self.settings["fastrouter"])),
                    "--master",
                    "--processes=4",
                    "--subscriptions-sign-check=SHA1:{0}".format(os.path.join(self.trunk.forest_root, "keys"))
                ],
                bufsize=1,
                close_fds=True
            )
            code = fastrouter.wait()

            assert code == 0, "Error starting fastrouter"
            log_message("Started fastrouter", component="Air")

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
        log_message("Stopping uwsgi fastrouter", component="Air")
        subprocess.call([self.__uwsgi_binary, "--stop", self.__pid_file])
        os.remove(self.__pid_file)