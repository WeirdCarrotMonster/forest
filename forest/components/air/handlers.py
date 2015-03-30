# -*- coding: utf-8 -*-

from __future__ import unicode_literals, print_function

from tornado import gen
import simplejson as json
from bson import json_util

from forest.components.api.decorators import token_auth
from forest.components.api.handler import Handler


class HostHandler(Handler):

    @gen.coroutine
    @token_auth
    def post(self):
        """
        POST-запросы, поступающие на апи обработки хостов, должны содержать информацию о добавляемом хосте.
        Имя хоста, указанное в поле host, будет добавлено в список разрешенных для подключения к
        uwsgi-router.
        """
        data = json.loads(self.request.body)
        assert "host" in data

        self.application.air.allow_host(data["host"])
        self.finish(json.dumps({}, default=json_util.default))