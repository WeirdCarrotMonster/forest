# coding=utf-8
"""Описывает объекты для работы с прокси-сервером."""

import os
import shutil

from forest.components.emperor import Vassal
from forest.components.common import log_message


class Fastrouter(Vassal):

    """Обертка вокруг uwsgi-fastrouter, сконфигурированная для запуска через emperor."""

    def __init__(self, host, port, fastrouter, keydir, **kwargs):
        """Инициализирует обертку uwsgi-fastrouter.

        :param host: Хост, на котором fastrouter-subscription-server будет ожидать подписок
        :type host: str
        :param port: Порт, на котором fastrouter будет ждать входящих запросов
        :type port: int
        :param fastrouter: Порт, на котором fastrouter-subscription-server будет ждать подписок
        :type fastrouter: int
        :param keydir: Полный путь к директории с публичными ключами доменов
        :type keydir: str
        """
        super(Fastrouter, self).__init__(**kwargs)
        self.host = host
        self.port = port
        self.keydir = keydir
        self.fastrouter = fastrouter

    def __get_config__(self):
        """Генерирует конфигурационный файл uwsgi-fastrouter.

        :returns: Строка конфигурации uwsgi-fastrouter
        :rtype: str
        """
        return """[uwsgi]
fastrouter=127.0.0.1:{port}
fastrouter-subscription-server={host}:{fastrouter}
subscriptions-sign-check=SHA1:{keydir}
""".format(port=self.port, host=self.host, fastrouter=self.fastrouter, keydir=self.keydir)


class Air(object):

    """Класс синглтона, работающего с прокси-сервером."""

    def __init__(self, trunk, host, fastrouter, port=3000):
        """Инициализирует компонент Air.

        :param trunk: Корневой объект ноды леса
        :type trunk: Trunk
        :param host: Хост, на котором fastrouter-subscription-server будет ждать подписок
        :type host: str
        :param fastrouter: Порт, на котором fastrouter-subscription-server будет ждать подписок
        :type fastrouter: int
        :param port: Порт, на котором fastrouter будет ждать входящих запросов
        :type port: int
        """
        self.trunk = trunk

        self.__fastrouter__ = Fastrouter(
            host=host,
            port=port,
            fastrouter=fastrouter,
            keydir=self.keydir,
            _id="fastrouter"
        )
        self.trunk.emperor.start_vassal(self.__fastrouter__)
        log_message("Started air", component="Air")

    @property
    def keydir(self):
        """Генерирует полный путь к директории с ключами.

        :returns: Полный путь к директории с ключами
        :rtype str
        """
        return os.path.join(self.trunk.forest_root, "keys")

    @property
    def settings(self):
        """Возвращает словарь настроек прокси-сервера.

        :returns: Словарь настроек
        :rtype: str
        """
        return {
            "host": self.__fastrouter__.host,
            "fastrouter": self.__fastrouter__.fastrouter
        }

    def allow_host(self, host):
        """Добавляет указанный хост в список разрешенных к подключению.

        Добавление представляет из себя создание публичного файла ключа в с заданным именем
        формата <hostname>.pem в директории ключей.

        :param host: Добавляемый в разрешенные хост
        :type host: str
        """
        default_key = os.path.join(self.keydir, "default.pem")

        key_file = os.path.join(self.keydir, host + ".pem")

        if not os.path.isfile(key_file):
            log_message("Creating key for address: {0}".format(host), component="Air")
            shutil.copyfile(default_key, key_file)
