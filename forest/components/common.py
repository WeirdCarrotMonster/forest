# coding=utf-8
"""Общие функции, повсеместно используемые в коде."""

from __future__ import print_function, unicode_literals

from datetime import datetime

import simplejson
from tornado.httpclient import AsyncHTTPClient, HTTPError
from tornado.gen import coroutine, Return
from bson import json_util


def log_message(message, component="Forest", end="\n", begin=""):
    """Логгирует событие леса в консоль.

    :param message: Логгируемое сообщение
    :type message: str
    :param component: Имя компонента, отправляющего сообщение
    :type component: str
    :param end: Символ, устанавливаемый на конце строки
    :type end: str
    :param begin: Символ, устанавливаемый на начале строки
    :type begin: str
    """
    print("{3}[{0}][{1}] {2}".format(datetime.now(), component.center(10), message, begin), end=end)


def loads(data):
    """Загружает json из строки.

    :param data: Строка с данными
    :type data: str
    :returns: Результат разбора строки
    :rtype: dict
    """
    return simplejson.loads(data, object_hook=json_util.object_hook)


def load(fp):
    """Загружает json из файла.

    :param fp: Файл с данными
    :type fp: file
    :returns: Результат разбора файла
    :rtype: dict
    """
    return simplejson.load(fp, object_hook=json_util.object_hook)


def dumps(data):
    """Сохраняет json в строку.

    :param data: Объект с данными
    :type data: dict
    :returns: Сохраненная строка
    :rtype: str
    """
    return simplejson.dumps(data, default=json_util.default)


def dump(data, fp):
    """Сохраняет json в файл.

    :param data: Объект с данными
    :type data: dict
    :returns: Результат сохранения файла
    """
    return simplejson.dump(data, fp, default=json_util.default)


@coroutine
def send_request(host, resource, method, data=None):
    """Асинхронно отправляет запрос.

    :param host: Хост, на который выполняется запрос
    :type host: str
    :param resource: Адрес ресурса на сервере
    :type resource: str
    :param method: Метод запроса
    :type method: str
    :param data: Передаваемые в запросе данные
    :type data: dict
    :returns: Ответ сервера и его код
    :rtype: tuple
    """
    http_client = AsyncHTTPClient()

    try:
        response = yield http_client.fetch(
            "http://{}:{}/api/{}".format(host["host"], host["port"], resource),
            body=dumps(data) if data else None,
            method=method,
            headers={"Token": host["secret"]}
        )
        data = response.body
        code = response.code
    except HTTPError as e:
        data = ""
        code = e.code

    try:
        data = loads(data)
    finally:
        raise Return((data, code))
