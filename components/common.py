# -*- coding: utf-8 -*-

from __future__ import print_function, unicode_literals

from datetime import datetime

import simplejson
from tornado.httpclient import AsyncHTTPClient, HTTPError
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

    def __exit__(self, m_type, value, traceback):
        if self.httpclient.interactive and traceback:
            self.httpclient.write(str(traceback))
            self.httpclient.flush()


def log_message(message, component="Forest", end="\n", begin=""):
    print("{3}[{0}][{1:8}] {2}".format(datetime.now(), component, message, begin), end=end)


def loads(data):
    return simplejson.loads(data, object_hook=json_util.object_hook)


def load(data):
    return simplejson.load(data, object_hook=json_util.object_hook)


def dumps(data):
    return simplejson.dumps(data, default=json_util.default)


def dump(data):
    return simplejson.dump(data, default=json_util.default)


@coroutine
def send_request(host, resource, method, data=None):
    http_client = AsyncHTTPClient()

    try:
        if data:
            response = yield http_client.fetch(
                "http://{}:{}/api/{}".format(host["host"], host["port"], resource),
                body=dumps(data),
                method=method,
                headers={"Token": host["secret"]}
            )
        else:
            response = yield http_client.fetch(
                "http://{}:{}/api/{}".format(host["host"], host["port"], resource),
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
