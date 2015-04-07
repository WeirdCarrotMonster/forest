# coding=utf-8
"""Описывает класс брокера системы - Druid."""

from collections import defaultdict

from pymongo.errors import AutoReconnect, ConnectionFailure, DuplicateKeyError
from tornado import gen
from toro import Lock


# pylint: disable=W0702


class Druid(object):

    """Класс брокера системы."""

    def __init__(self, trunk, settings):
        """Инициализирует настройки брокера.

        :param trunk:
        :type trunk:
        :param settings:
        :type settings:
        """
        self.trunk = trunk
        self.__air__ = settings.get("air", [])
        self.__roots__ = settings.get("roots", [])
        self.__branch__ = settings.get("branch", [])
        self.__log_listeners__ = defaultdict(set)

        self.creation_lock = Lock()

    def add_listener(self, leaf_id, listener):
        """Добавляет слушателя логов.

        :param leaf_id:
        :type leaf_id:
        :param listener:
        :type listener:
        """
        self.__log_listeners__[leaf_id].add(listener)

    def remove_listener(self, leaf_id, listener):
        """Удаляет слушателя логов.

        :param leaf_id:
        :type leaf_id:
        :param listener:
        :type listener:
        """
        if listener in self.__log_listeners__[leaf_id]:
            self.__log_listeners__[leaf_id].remove(listener)

    @gen.coroutine
    def store_log(self, log):
        """Сохраняет лог в БД.

        :param log: Сохраняемые данные
        :type log: dict
        """
        for _ in range(10):
            try:
                yield self.trunk.async_db.logs.insert(log)
                break
            except (AutoReconnect, ConnectionFailure):
                yield gen.sleep(2)
            except DuplicateKeyError:
                pass

    @gen.coroutine
    def propagate_event(self, event):
        """Передает событие всем слушателям, заинтересованным в нем.

        :param event: Распространяемое событие
        :type event: dict
        """
        leaf = str(event.get("log_source"))
        yield self.store_log(event)

        for l in self.__log_listeners__[leaf]:
            try:
                l.put(event)
            except:
                pass

    @property
    def air(self):
        """Объект-обертка прокси сервера.

        :returns: Прокси-сервер
        :rtype: Air
        """
        return self.__air__

    @property
    def roots(self):
        """Объект-обертка сервера управления БД.

        :returns: Сервер управления базами.
        :rtype: Roots
        """
        return self.__roots__

    @property
    def branch(self):
        """Объект-обертка сервера приложений.

        :returns: Сервер приложений
        :rtype: Branch
        """
        return self.__branch__
