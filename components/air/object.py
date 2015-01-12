# -*- coding: utf-8 -*-
import os
import shutil
import subprocess

from components.common import log_message


class Air():
    def __init__(self, trunk, host, fastrouter, port=3000):
        self.trunk = trunk
        self.__host = host
        self.__fastrouter = fastrouter
        self.__port = port
        self.__uwsgi_binary = os.path.join(self.trunk.forest_root, "bin/uwsgi")
        self.__pid_file = os.path.join(self.trunk.forest_root, "fastrouter.pid")
        self.__key_dir = os.path.join(self.trunk.forest_root, "keys")

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
                    "--fastrouter=127.0.0.1:{}".format(self.__port),
                    "--pidfile={}".format(self.__pid_file),
                    "--daemonize=/dev/null",
                    "--fastrouter-subscription-server={}:{}".format(
                        self.__host,
                        self.__fastrouter
                    ),
                    "--master", "--processes=4",
                    "--subscriptions-sign-check=SHA1:{}".format(self.__key_dir)
                ],
                bufsize=1,
                close_fds=True
            )
            code = fastrouter.wait()

            assert code == 0, "Error starting fastrouter"
            log_message("Started fastrouter", component="Air")

        self.last_update = None

    @property
    def settings(self):
        return {
            "host": self.__host,
            "fastrouter": self.__fastrouter
        }

    def allow_host(self, host):
        default_key = os.path.join(self.__key_dir, "default.pem")

        key_file = os.path.join(self.trunk.forest_root, "keys/{}.pem".format(host))

        if not os.path.isfile(key_file):
            log_message("Creating key for address: {0}".format(host), component="Air")
            shutil.copyfile(default_key, key_file)

    def cleanup(self):
        log_message("Stopping uwsgi fastrouter", component="Air")
        subprocess.call([self.__uwsgi_binary, "--stop", self.__pid_file])
        os.remove(self.__pid_file)
