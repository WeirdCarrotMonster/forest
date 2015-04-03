# -*- coding: utf-8 -*-

from __future__ import unicode_literals, print_function

from tornado import gen

from forest.components.common import dumps
from forest.components.api.decorators import token_auth, schema
from forest.components.api.handler import Handler

# pylint: disable=W0221


class HostHandler(Handler):

    """Хендлер для /api/air/hosts."""

    @gen.coroutine
    @token_auth
    @schema("air.host")
    def post(self, host):
        """Добавляет передаваемый в параметре host в список разрешенных.

        :param host: Хостнейм, разрешаемый в системе
        :type host: str
        """
        self.application.air.allow_host(host)
        self.finish(dumps({"result": "success"}))
