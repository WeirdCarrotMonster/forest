# -*- coding: utf-8 -*-

import simplejson as json
from bson import ObjectId
from components.common import log_message


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
                 active=False,
                 modified=None,
                 **kwargs
                 ):
        self.__keyfile = keyfile
        self.fastrouters = fastrouters or []
        self.emperor_dir = None
        self.__species__ = species
        self.batteries = batteries
        self._log_port = None
        self.settings = settings or {}
        self.modified = modified
        self.address = address
        self.workers = workers
        self.threads = threads
        self.branch = branch or []
        self.active = active
        self.__name = name
        self._id = ObjectId(_id)
        self.paused = False

        self.__status__ = "stopped"
        self.__emperor__ = emperor

    def __ne__(self, other):
        r1 = self.address == other.address
        r2 = self.settings == other.settings
        r3 = self.workers == other.workers
        r4 = self.batteries == other.batteries
        r5 = self.modified == other.modified
        return not all([r1, r2, r3, r4, r5])

    def restarted(self, other):
        r1 = self.address == other.address
        r2 = self.settings == other.settings
        r3 = self.workers == other.workers
        r4 = self.batteries == other.batteries
        return all([r1, r2, r3, r4])

    def start(self):
        if self.__species__.is_ready:
            self.__emperor__.start_leaf(self)
            self.__status__ = "started"
            log_message("Starting leaf {}".format(self.id), component="Leaf")
            return True
        log_message("Queued leaf {}".format(self.id), component="Leaf")
        return False

    def stop(self):
        log_message("Stopping leaf {}".format(self.id), component="Leaf")
        self.__emperor__.stop_leaf(self)
        self.__status__ = "stopped"

    @property
    def status(self):
        return self.__status__

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
        return self.__species__

    @species.setter
    def species(self, value):
        self.__species__ = value

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
        if not self.paused:
            return self.__get_config()
        else:
            return self.__get_config_paused()

    def __get_config_paused(self):
        return """
[uwsgi]
"""

    def __get_config(self):
        logs_format = {
            "uri": "%(uri)",
            "method": "%(method)",
            "addr": "%(addr)",
            "host": "%(host)",
            "proto": "%(proto)",
            "status": "%(status)",
            "msecs": "%(msecs)",
            "time": "%(ltime)",
            "response_size": "%(size)",
            "request_size": "%(cl)",
            "log_source": str(self.id)
        }

        config = """[uwsgi]
chdir={chdir}
plugin={python}
module=wsgi:application
processes={workers}
env=BATTERIES={batteries}
env=APPLICATION_SETTINGS={app_settings}
env=VIRTUAL_ENV={virtualenv}
virtualenv={virtualenv}
logformat={logformat}
static-map=/static={chdir}/static
offload-threads=4
log-encoder=prefix [Leaf {id}]
need-app=
if-env=PATH
env=PATH={virtualenv}/bin:%(_)
endif=
""".format(
            chdir=self.__species__.src_path,
            virtualenv=self.__species__.environment,
            app_settings=json.dumps(self.settings),
            batteries=json.dumps(self.batteries),
            logformat=json.dumps(logs_format),
            workers=self.workers,
            id=self.id,
            python=self.__species__.python_version
        )
        if self.threads:
            config += "enable-threads=1\n"

        for before_start in self.__species__.triggers.get("before_start", []):
            config += "hook-pre-app=exec:{}\n".format(before_start)

        for router in self.fastrouters:
            for address in self.address:
                config += "subscribe-to={0}:{1},5,SHA1:{2}\n".format(
                    router,
                    address, self.keyfile)

        return config
