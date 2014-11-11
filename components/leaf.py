# -*- coding: utf-8 -*-
import datetime
import os

import simplejson as json


class Leaf(object):
    statuses = (
        (0, "Stopped"),
        (1, "Started"),
        (2, "Waiting: trigger before_start"),
        (3, "Waiting: environment")
    )

    def __init__(self,
                 name=None,
                 _id=None,
                 branch_settings=None,
                 settings=None,
                 fastrouters=None,
                 address=None,
                 batteries=None,
                 workers=4,
                 threads=False,
                 species=None,
                 emperor=None,
                 branches=None,
                 **kwargs
                 ):
        self.__branch_settings = branch_settings or {}
        self.fastrouters = fastrouters or []
        self.emperor_dir = None
        self.__species = species
        self.__emperor = emperor
        self.batteries = batteries
        self._log_port = None
        self.branches = branches or []
        self.settings = settings or {}
        self.address = address
        self.workers = workers
        self.threads = threads
        self.__name = name
        self._id = _id

    def __ne__(self, other):
        r1 = self.address == other.address
        r2 = self.settings == other.settings
        r3 = self.workers == other.workers
        r4 = self.batteries == other.batteries
        return not all([r1, r2, r3, r4])

    @property
    def running(self):
        return self._id in self.__emperor

    @property
    def should_be_running(self):
        return True

    @property
    def id(self):
        return self._id

    @property
    def name(self):
        return self.__name

    @property
    def keyfile(self):
        return self.__branch_settings.get("keyfile")

    @property
    def log_port(self):
        return self._log_port

    @property
    def species(self):
        return self.__species

    @log_port.setter
    def log_port(self, value):
        self._log_port = value

    @property
    def environment(self):
        return {
            "BATTERIES": json.dumps(self.batteries),
            "APPLICATION_SETTINGS": json.dumps(self.settings)
        }

    def get_config(self):
        logs_format = {
            "uri": "%(uri)",
            "method": "%(method)",
            "addr": "%(addr)",
            "host": "%(host)",
            "proto": "%(proto)",
            "status": "%(status)",
            "msecs": "%(msecs)",
            "time": "%(ltime)",
            "size": "%(size)",
            "log_source": str(self.id)
        }

        config = """
[uwsgi]
chdir={chdir}
processes={workers}
env=BATTERIES={batteries}
env=APPLICATION_SETTINGS={app_settings}
logformat={logformat}
virtualenv={virtualenv}
static-map=/static={chdir}/static
log-encoder = prefix [Leaf {id}]
        """.format(
            chdir=self.__species.path,
            virtualenv=self.__species.environment,
            app_settings=json.dumps(self.settings),
            batteries=json.dumps(self.batteries),
            logformat=json.dumps(logs_format),
            workers=self.workers,
            id=self.id
        )
        if self.threads:
            config += "enable-threads=1\n"

        for before_start in self.__species.triggers.get("before_start", []):
            config += "hook-pre-app=exec:{}\n".format(before_start)

        for router in self.fastrouters:
            for address in self.address:
                config += "subscribe-to={0}:{1},5,SHA1:{2}\n".format(
                    router,
                    address, self.keyfile)

        return config