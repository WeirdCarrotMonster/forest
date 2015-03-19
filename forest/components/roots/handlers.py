# -*- coding: utf-8 -*-

from __future__ import unicode_literals, print_function

from tornado import gen
import simplejson as json
from bson import json_util

from forest.components.api.handler import Handler


class DatabaseHandler(Handler):

    @gen.coroutine
    def post(self):
        """
        POST-запросы, поступающие на апи обработки хостов, должны содержать информацию о добавляемом хосте.
        Имя хоста, указанное в поле host, будет добавлено в список разрешенных для подключения к
        uwsgi-router.
        """
        data = json.loads(self.request.body, object_hook=json_util.object_hook)
        assert "name" and "db_type" in data

        credentials = yield self.application.roots.create_db(str(data["name"]), data["db_type"])
        self.finish(json.dumps(credentials, default=json_util.default))
