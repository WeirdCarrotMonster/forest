# coding=utf-8
"""Описывает хендлеры для API прокси-сервера."""

from __future__ import unicode_literals, print_function

from forest.components.api.decorators import token_auth
from forest.components.api.handler import Handler
from forest.components.common import dumps
from forest.jsonschema.decorators import schema
from tornado import gen


# pylint: disable=W0221


class HostHandler(Handler):

    """Хендлер для /api/air/hosts."""

    @gen.coroutine
    @token_auth
    @schema("air.hosts")
    def post(self, host):
        """Добавляет передаваемый в параметре host в список разрешенных.

        :param host: Хостнейм, разрешаемый в системе
        :type host: str
        """
        self.application.air.allow_host(host)
        self.finish(dumps({"result": "success"}))
