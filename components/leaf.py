# -*- coding: utf-8 -*-
import datetime
import os

import simplejson as json


class Leaf(object):
    def __init__(self,
                 name=None,
                 _id=None,
                 keyfile=None,
                 settings=None,
                 fastrouters=None,
                 address=None,
                 batteries=None,
                 workers=4,
                 threads=False,
                 species=None,
                 emperor=None,
                 branch=None,
                 trunk=None,
                 active=False,
                 modified=None,
                 locked=None,
                 tasks=None,
                 **kwargs
                 ):
        self.__keyfile = keyfile
        self.fastrouters = fastrouters or []
        self.emperor_dir = None
        self.__species = species
        self.__emperor = emperor
        self.batteries = batteries
        self._log_port = None
        self.settings = settings or {}
        self.modified = modified
        self.address = address
        self.workers = workers
        self.threads = threads
        self.branch = branch or []
        self.locked = locked
        self.active = active
        self.__name = name
        self.tasks = tasks or []
        self.trunk = trunk
        self._id = _id

    def __ne__(self, other):
        r1 = self.address == other.address
        r2 = self.settings == other.settings
        r3 = self.workers == other.workers
        r4 = self.batteries == other.batteries
        r5 = self.modified == other.modified
        return not all([r1, r2, r3, r4, r5])

    @property
    def running(self):
        return self._id in self.__emperor.vassal_names

    @property
    def should_be_running(self):
        return self.active and not self.locked and self.trunk.id in self.branch and not self.tasks

    @property
    def queued(self):
        return self._id in self.trunk.branch.leaves

    @property
    def id(self):
        return self._id

    @property
    def name(self):
        return self.__name

    @property
    def keyfile(self):
        return self.__keyfile

    @property
    def log_port(self):
        return self._log_port

    @property
    def species(self):
        """
        Возвращает объект типа листа,

        :rtype : Species
        :return:
        """
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
plugin={python}
module=wsgi:application
processes={workers}
env=BATTERIES={batteries}
env=APPLICATION_SETTINGS={app_settings}
logformat={logformat}
virtualenv={virtualenv}
static-map=/static={chdir}/static
offload-threads=4
log-encoder = prefix [Leaf {id}]
        """.format(
            chdir=self.__species.src_path,
            virtualenv=self.__species.environment,
            app_settings=json.dumps(self.settings),
            batteries=json.dumps(self.batteries),
            logformat=json.dumps(logs_format),
            workers=self.workers,
            id=self.id,
            python=self.__species.python_version
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