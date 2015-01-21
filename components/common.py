# -*- coding: utf-8 -*-

from __future__ import print_function, unicode_literals

from datetime import datetime

from simplejson import dumps, loads
from tornado.httpclient import AsyncHTTPClient
from tornado.gen import coroutine, Return
from bson import json_util


class LogicError(Exception):
    pass


class Message(object):

    def __init__(self, httpclient, message):
        self.httpclient = httpclient
        self.message = message

    def __enter__(self):
        if self.httpclient.interactive:
            self.httpclient.write(self.message)
            self.httpclient.flush()
        return None

    def __exit__(self, type, value, traceback):
        if self.httpclient.interactive and traceback:
            self.httpclient.write(str(traceback))
            self.httpclient.flush


def log_message(message, component="Forest", end="\n", begin=""):
    print("{3}[{0}][{1:8}] {2}".format(datetime.now(), component, message, begin), end=end)


@coroutine
def send_post_request(host, resource, data):
    """
    Отправляет POST-запрос на host, передавая в теле json-encoded data

    :param host: Данные о хосте
    :type host: dict
    :param resource: Запрашиваемый ресурс
    :type resource: unicode
    :param data: Отправляемые данные
    :type data: dict
    :return: Ответ ресурса
    :rtype: dict
    """
    http_client = AsyncHTTPClient()

    response = yield http_client.fetch(
        "http://{}:{}/api/{}".format(host["host"], host["port"], resource),
        body=dumps(data, default=json_util.default),
        method="POST",
        headers={"Token": host["secret"]},
    )

    try:
        parsed = {
            "data": loads(response.body, object_hook=json_util.object_hook),
            "code": response.code
        }
    except:
        parsed = {
            "code": response.code,
            "data": response.body
        }
    raise Return(parsed)


@coroutine
def send_request(host, resource, method, data=None):
    http_client = AsyncHTTPClient()

    if data:
        response = yield http_client.fetch(
            "http://{}:{}/api/{}".format(host["host"], host["port"], resource),
            body=dumps(data, default=json_util.default),
            method=method,
            headers={"Token": host["secret"]}
        )
    else:
        response = yield http_client.fetch(
            "http://{}:{}/api/{}".format(host["host"], host["port"], resource),
            method=method,
            headers={"Token": host["secret"]}
        )

    try:
        data = loads(response.body, object_hook=json_util.object_hook)
    except:
        data = response.body
    raise Return((data, response.code))
