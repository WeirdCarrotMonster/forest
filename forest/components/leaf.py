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
buffer-size=65535
heartbeat=10
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
{triggers}
""".format(
            leaf_data_dict=dumps(self.dict),
            chdir=self.__species__.src_path,
            virtualenv=self.__species__.environment,
            app_settings=dumps(self.settings),
            batteries=dumps(self.__batteries__),
            logformat=dumps(logs_format),
            workers=self.workers,
            id=self.id,
            python=self.__species__.python,
            leaf_host=self.leaf_host,
            log_port=self.log_port,
            cron=self.get_cron_config(),
            triggers=self.get_triggers_config(),
            mules=self.get_mules_config()
        )
        if self.threads:
            config += "enable-threads=1\n"

        for router, address in product(self.__fastrouters__, self.address):
            config += "subscribe-to={0}:{1},5,SHA1:{2}\n".format(
                router,
                address, self.keyfile
            )

        return config
