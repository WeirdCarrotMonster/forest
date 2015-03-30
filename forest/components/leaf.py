# -*- coding: utf-8 -*-

from itertools import product

from forest.components.emperor import Vassal
from forest.components.common import dumps


class Leaf(Vassal):

    def __init__(self,
                 address=None,
                 batteries=None,
                 fastrouters=None,
                 keyfile=None,
                 leaf_host=None,
                 log_port=None,
                 settings=None,
                 species=None,
                 threads=False,
                 workers=2,
                 **kwargs
                 ):
        super(Leaf, self).__init__(**kwargs)
        self.__keyfile__ = keyfile
        self.__fastrouters__ = fastrouters or []
        self.__species__ = species
        self.__batteries__ = batteries
        self.__log_port__ = log_port
        self.settings = settings or {}
        self.address = address
        self.workers = workers
        self.threads = threads
        self.leaf_host = leaf_host

    def start(self):
        """Запускает лист

        Перед непосредственным запуском метод выполняет проверку текущего состояния вида - если он готов, то выполняется
        непосредственный запуск листа, иначе лист изменяет состояние на "Queued" и встает в очередь ожидания
        """
        if self.__species__.is_ready:
            super(Leaf, self).start()
            return True
        self.status = "Queued"
        return False

    @property
    def keyfile(self):
        """Используемый при аутентификации с fastrouter'ом файл ключа
        :returns: Полный путь к файлу ключа
        :rtype: str
        """
        return self.__keyfile__

    @property
    def log_port(self):
        """Локальный порт, на который будут отправляться все логи событий
        :returns: Номер порта логов
        :rtype: int
        """
        return self.__log_port__

    @property
    def dict(self):
        """Словарь с конфигурацией листа, по которой можно провести его создание
        :returns: Словарь со значением всех полей экземпляра листа
        :rtype: dict
        """
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
        """Используемый тип листа
        :returns: Экземпляр типа листа
        :rtype: Species
        """
        return self.__species__

    @species.setter
    def species(self, value):
        """Устанавливает используемый тип листа
        :param value: Экземпляр типа листа
        :type value: Species
        """
        self.__species__ = value

    def pause(self):
        """Приостанавливает работу листа

        Приостановление работы отличается от полной остановки тем, что в отличии от остановки не удаляет
        конфигурационный файл полностью, а заменяет его на используемый для отображения заглушки
        """
        self.status = "Paused"
        # TODO: Раскомментировать, когда будет работать приостановленный конфиг
        # self.__emperor__.start_vassal(self)
        self.__emperor__.stop_vassal(self)

    def get_config(self):
        """Переопределенный метод получения конфигурации uwsgi-вассала

        Метод get_config листа отличается от оригинального тем, что возвращает разную конфигурацию в зависимости от
        текущего статуса: обычную, в случае, если лист запущен и заглушку, если лист остановлен.
        :returns: Конфигурация uwsgi-вассала
        :rtype: str
        """
        if self.status != "Paused":
            return self.__get_config__()
        else:
            return self.__get_config_paused__()

    def __get_config_paused__(self):
        """Конфигурация листа в приостановленном состоянии
        :returns: Конфигурация uwsgi-вассала
        :rtype: str

        .. todo::
            Описать конфигурацию для приложения-заглушки, которое будет передавать только страницу с сообщением о
            проведении технических работ
        """
        return """[uwsgi]"""

    def __get_config__(self):
        """Конфигурация листа в нормальном состоянии
        :returns: Конфигурация uwsgi-вассала
        :rtype: str
        """
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
            virtualenv=self.species.environment,
            workers=self.workers
        )

        for router, address in product(self.__fastrouters__, self.address):
            config += "subscribe-to={0}:{1},5,SHA1:{2}\n".format(
                router,
                address, self.keyfile
            )

        return config
