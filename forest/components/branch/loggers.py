# coding=utf-8
"""Описывает классы логгеров событий."""

from __future__ import unicode_literals, print_function
from tornado import gen
import simplejson as json
from bson import json_util
from tornado.httpclient import AsyncHTTPClient


# pylint: disable=W0702,W0612,W0613


class Logger(object):

    """Базовый класс логгера."""

    class LoggerCreationError(Exception):
        pass

    def __init__(
            self,
            identifier,
            filters=None,
            max_failures=0,
            redundant_keys=None,
            **kwargs
            ):
        """Инициализирует логгер.

        :param identifier: Уникальный идентификатор логгера
        :type identifier: str
        :param filters: Фильтры сообщений логгера
        :type filters: dict
        :param max_failures: Максимальное количество допустимых ошибок подряд
        :type max_failures: int
        :param redundant_keys: Исключаемые из ответа ключи
        :type redundant_keys: list
        """
        self.__max_failures__ = max_failures
        self.__filters__ = filters or {}
        self.__failures__ = 0
        self.__redundant_keys__ = redundant_keys or []
        self.identifier = identifier

    @property
    def failed(self):
        """Флаг ошибки работы логгера.

        :returns: Статус флага ошибки.
        :rtype: bool
        """
        if self.__max_failures__ == 0:
            return False

        return self.__failures__ >= self.__max_failures__

    def suitable(self, log):
        """Проверяет, подходит ли логгер для отправки сообщения.

        :param log: Логгируемое сообщение
        :type log: dict
        """
        for key, value in self.__filters__.items():
            if not (key in log and log[key] == value):
                return False

        return True

    @gen.coroutine
    def log(self, data):
        """Выполняет сохранение лога.

        :param data: Сохраняемый лог
        :type data: dict
        """
        if not data:
            return

        try:
            yield self.__log__(
                self.__prepare_data__(data)
            )
        except:
            import traceback
            print(traceback.format_exc())
            self.__error__()
        else:
            self.__success__()

    def __prepare_data__(self, data):
        """Подготавливает лог к отправке.

        :param data: Сохраняемый лог
        :type data: dict
        :returns: Подготовленный к отправке лог
        :rtype: dict
        """
        __data__ = dict(data)

        for key in self.__redundant_keys__:
            if key in __data__:
                del __data__[key]

        return __data__

    @gen.coroutine
    def __log__(self, data):
        """Логгирует сообщение.

        Метод должен быть переопределен в классе-потомке.

        :param data: Сохраняемый лог
        :type data: dict
        """
        raise NotImplementedError

    def __success__(self):
        """Обрабатывает событие успешного логгирования."""
        self.__failures__ = 0

    def __error__(self):
        """Обрабатывает событие ошибки логгирования."""
        self.__failures__ += 1


class POSTLogger(Logger):

    """Логгер, отправляющий сообщения через POST-запросы."""

    def __init__(
            self,
            address,
            headers=None,
            connect_timeout=5,
            request_timeout=5,
            *args,
            **kwargs
            ):
        """Инициализирует POST-логгер.

        :param address: Адрес, на который отправляется POST-запрос
        :type address: str
        :param headers: Дополнительные хедеры POST-запроса
        :type headers: dict
        :param connect_timeout: Таймаут подключения к серверу
        :type connect_timeout: int
        :param request_timeout: Таймаут отправки запроса
        :type request_timeout: int
        """
        super(POSTLogger, self).__init__(*args, **kwargs)
        self.__address__ = address
        self.__headers__ = headers or {}
        self.__ctimeout__ = connect_timeout
        self.__rtimeout__ = request_timeout

    @gen.coroutine
    def __log__(self, data):
        """Логгирует сообщение.

        :param data: Сохраняемый лог
        :type data: dict
        """
        yield AsyncHTTPClient().fetch(
            self.__address__,
            body=json.dumps(data, default=json_util.default),
            method="POST",
            headers=self.__headers__,
            connect_timeout=self.__ctimeout__,
            request_timeout=self.__rtimeout__
        )
