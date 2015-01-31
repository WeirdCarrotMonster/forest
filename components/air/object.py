# -*- coding: utf-8 -*-
import os
import shutil

from components.emperor import Vassal
from components.common import log_message


class Fastrouter(Vassal):

    def __init__(self, host, port, fastrouter, keydir, **kwargs):
        super(Fastrouter, self).__init__(**kwargs)
        self.host = host
        self.port = port
        self.keydir = keydir
        self.fastrouter = fastrouter

    def __get_config__(self):
        return """[uwsgi]
fastrouter=127.0.0.1:{port}
fastrouter-subscription-server={host}:{fastrouter}
master=true
processes=4
subscriptions-sign-check=SHA1:{keydir}
""".format(port=self.port, host=self.host, fastrouter=self.fastrouter, keydir=self.keydir)


class Air():

    def __init__(self, trunk, host, fastrouter, port=3000):
        self.trunk = trunk

        self.__fastrouter__ = Fastrouter(
            host=host,
            port=port,
            fastrouter=fastrouter,
            keydir=self.keydir,
            _id="fastrouter",
            name="fastrouter"
        )
        self.trunk.emperor.start_vassal(self.__fastrouter__)
        log_message("Started air", component="Air")

    @property
    def keydir(self):
        return os.path.join(self.trunk.forest_root, "keys")

    @property
    def settings(self):
        return {
            "host": self.__fastrouter__.host,
            "fastrouter": self.__fastrouter__.fastrouter
        }

    def allow_host(self, host):
        default_key = os.path.join(self.keydir, "default.pem")

        key_file = os.path.join(self.keydir, host + ".pem")

        if not os.path.isfile(key_file):
            log_message("Creating key for address: {0}".format(host), component="Air")
            shutil.copyfile(default_key, key_file)
