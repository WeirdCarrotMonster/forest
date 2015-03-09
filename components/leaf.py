# -*- coding: utf-8 -*-

import simplejson as json

from components.emperor import Vassal
from components.common import log_message


class Leaf(Vassal):

    def __init__(self,
                 keyfile=None,
                 settings=None,
                 fastrouters=None,
                 address=None,
                 batteries=None,
                 workers=2,
                 threads=False,
                 species=None,
                 log_port=None,
                 leaf_host=None,
                 **kwargs
                 ):
        super(Leaf, self).__init__(**kwargs)
        self.__keyfile__ = keyfile
        self.__fastrouters__ = fastrouters or []
        self.__species__ = species
        self.__batteries__ = batteries
        self.__log_port__ = None
        self.settings = settings or {}
        self.address = address
        self.workers = workers
        self.threads = threads
        self.log_port = log_port
        self.leaf_host = leaf_host
        self.paused = False

    def start(self):
        if self.__species__.is_ready:
            super(Leaf, self).start()
            return True
        self.status = "Queued"
        return False

    @property
    def keyfile(self):
        return self.__keyfile__

    @property
    def log_port(self):
        return self.__log_port__

    @log_port.setter
    def log_port(self, value):
        self.__log_port__ = value

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

    @property
    def environment(self):
        return {
            "BATTERIES": json.dumps(self.__batteries__),
            "APPLICATION_SETTINGS": json.dumps(self.settings)
        }

    def get_config(self):
        if not self.paused:
            return self.__get_config__()
        else:
            return self.__get_config_paused__()

    def __get_config_paused__(self):
        return """[uwsgi]"""

    def __get_config__(self):
        logs_format = {
            "uri": "%(uri)",
            "addr": "%(addr)",
            "host": "%(host)",
            "time": "%(epoch)",
            "proto": "%(proto)",
            "msecs": "%(msecs)",
            "method": "%(method)",
            "status": "%(status)",
            "warning": "%(warning)",
            "request_size": "%(cl)",
            "response_size": "%(size)",
            "traceback": "%(traceback)",
            "log_source": str(self.id)
        }

        config = """[uwsgi]
master=1
socket={leaf_host}:0
logger=zeromq:tcp://127.0.0.1:{log_port}
req-logger=zeromq:tcp://127.0.0.1:{log_port}
buffer-size=65535
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

{mules}
{cron}
""".format(
            chdir=self.__species__.src_path,
            virtualenv=self.__species__.environment,
            app_settings=json.dumps(self.settings),
            batteries=json.dumps(self.__batteries__),
            logformat=json.dumps(logs_format),
            workers=self.workers,
            id=self.id,
            python=self.__species__.python_version,
            leaf_host=self.leaf_host,
            log_port=self.log_port,
            mules=self.get_mules_config(),
            cron=self.get_cron_config()
        )
        if self.threads:
            config += "enable-threads=1\n"

        for before_start in self.__species__.triggers.get("before_start", []):
            config += "hook-pre-app=exec:{}\n".format(before_start)

        for router in self.__fastrouters__:
            for address in self.address:
                config += "subscribe-to={0}:{1},5,SHA1:{2}\n".format(
                    router,
                    address, self.keyfile
                )

        return config
