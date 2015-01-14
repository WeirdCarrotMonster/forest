#coding=utf-8

from __future__ import unicode_literals
import tornado.web
import tornado.gen
import simplejson as json
from bson import ObjectId


class LeavesHandler(tornado.web.RequestHandler):
    """
    Выполняет управление каждым отдельно взятым листом
    """
    @tornado.gen.coroutine
    def get(self):
        """
        Возвращает список всех известных листьев
        """
        pass

    @tornado.gen.coroutine
    def post(self):
        data = json.loads(self.request.body)
        assert "_id" in data
        leaf = ObjectId(data["_id"])
        leaf_obj = yield self.application.branch.create_leaf(leaf)
        self.application.branch.start_leaf(leaf_obj)
        self.finish({"result": "success"})


class LeafHandler(tornado.web.RequestHandler):
    """
    Выполняет управление каждым отдельно взятым листом
    """
    @tornado.gen.coroutine
    def get(self):
        """
        Получает информацию о листе с указанным id
        """
        pass

    @tornado.gen.coroutine
    def post(self):
        """
        Перезаписывает настройки листа
        """
        pass

    @tornado.gen.coroutine
    def delete(self):
        """
        Удаляет лист
        """
        pass
