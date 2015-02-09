# coding=utf-8

from __future__ import unicode_literals, print_function
from tornado import gen
import simplejson as json
from bson import json_util
from tornado.httpclient import AsyncHTTPClient


class Logger(object):

    def __init__(self, identifier, max_failures=0, filters=None, *args, **kwargs):
        self.__max_failures__ = max_failures
        self.__filters__ = filters or {}
        self.__failures__ = 0
        self.identifier = identifier

    @property
    def failed(self):
        if self.__max_failures__ == 0:
            return False

        return self.__failures__ >= self.__max_failures__

    def suitable(self, log):
        """
        :param log: Логгируемое сообщение
        :type log: dict
        """
        for key, value in self.__filters__.items():
            if not (key in log and log[key] == value):
                return False

        return True

    @gen.coroutine
    def log(self, data):
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
        return data

    @gen.coroutine
    def __log__(self, data):
        raise NotImplementedError

    def __success__(self):
        self.__failures__ = 0

    def __error__(self):
        self.__failures__ += 1


class POSTLogger(Logger):

    def __init__(self, address, headers=None, connect_timeout=5, request_timeout=5, *args, **kwargs):
        super(POSTLogger, self).__init__(*args, **kwargs)
        self.__address__ = address
        self.__headers__ = headers or {}
        self.__ctimeout__ = connect_timeout
        self.__rtimeout__ = request_timeout

    @gen.coroutine
    def __log__(self, data):
        yield AsyncHTTPClient().fetch(
            self.__address__,
            body=json.dumps(data, default=json_util.default),
            method="POST",
            headers=self.__headers__,
            connect_timeout=self.__ctimeout__,
            request_timeout=self.__rtimeout__
        )


class POSTLoggerMinimal(POSTLogger):

    def __init__(self, redundant_keys, *args, **kwargs):
        super(POSTLoggerMinimal, self).__init__(*args, **kwargs)
        self.__redundant_keys__ = redundant_keys

    def __prepare_data__(self, data):
        __data__ = dict(data)

        for key in self.__redundant_keys__:
            if key in __data__:
                del __data__[key]

        return __data__
