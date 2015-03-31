# -*- coding: utf-8 -*-

from __future__ import unicode_literals, print_function

from tornado import gen

from forest.components.common import dumps
from forest.components.api.decorators import token_auth, schema
from forest.components.api.handler import Handler


class HostHandler(Handler):

    @gen.coroutine
    @token_auth
    @schema("air.host")
    def post(self):
        """
        POST-запросы, поступающие на апи обработки хостов, должны содержать информацию о добавляемом хосте.
        Имя хоста, указанное в поле host, будет добавлено в список разрешенных для подключения к
        uwsgi-router.
        """
        data = self.request.body

        self.application.air.allow_host(data["host"])
        self.finish(dumps({}))
