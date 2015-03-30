# -*- coding: utf-8 -*-

from itertools import product

from forest.components.emperor import Vassal
from forest.components.common import dumps


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
    def dict(self):
        data = super(Leaf, self).dict
        data.update({
            "settings": self.settings,
            "fastrouters": self.__fastrouters__,
            "address": self.address,
            "batteries": self.__batteries__,
            "workers": self.workers,
            "threads": self.threads,
            "type": self.__species__.id
        })
        return data

    @property
    def species(self):
        """Возвращает тип листа
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
            "BATTERIES": dumps(self.__batteries__),
            "APPLICATION_SETTINGS": dumps(self.settings)
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

        config = """[forest]
data={leaf_data_dict}

[uwsgi]
master=1
need-app=
buffer-size=65535
heartbeat=10
socket={leaf_host}:0

logger=zeromq:tcp://127.0.0.1:{log_port}
req-logger=zeromq:tcp://127.0.0.1:{log_port}
logformat={logformat}
log-encoder=prefix [Leaf {id}]

plugin={python}
module=wsgi:application
processes={workers}
static-map=/static={chdir}/static
offload-threads=4
{threads}

chdir={chdir}
env=BATTERIES={batteries}
env=APPLICATION_SETTINGS={app_settings}
env=VIRTUAL_ENV={virtualenv}

virtualenv={virtualenv}
if-env=PATH
env=PATH={virtualenv}/bin:%(_)
endif=

{mules}
{cron}
{triggers}
""".format(
            app_settings=dumps(self.settings),
            batteries=dumps(self.__batteries__),
            chdir=self.__species__.src_path,
            cron=self.get_cron_config(),
            id=self.id,
            leaf_data_dict=dumps(self.dict),
            leaf_host=self.leaf_host,
            log_port=self.log_port,
            logformat=dumps(logs_format),
            mules=self.get_mules_config(),
            python=self.__species__.python,
            threads="enable-threads=" if self.threads else "",
            triggers=self.get_triggers_config(),
            virtualenv=self.__species__.environment,
            workers=self.workers
        )

        for router, address in product(self.__fastrouters__, self.address):
            config += "subscribe-to={0}:{1},5,SHA1:{2}\n".format(
                router,
                address, self.keyfile
            )

        return config
