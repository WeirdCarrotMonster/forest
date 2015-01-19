# coding=utf-8

from __future__ import unicode_literals
import tornado.web
import tornado.gen
import simplejson as json
from bson import ObjectId, json_util


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
        data = json.loads(self.request.body, object_hook=json_util.object_hook)

        leaf = yield self.application.branch.create_leaf(data)
        started = self.application.branch.add_leaf(leaf)

        self.finish({"result": "started" if started else "queued"})


class LeafHandler(tornado.web.RequestHandler):

    """
    Выполняет управление каждым отдельно взятым листом
    """
    @tornado.gen.coroutine
    def get(self, _id):
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
    def delete(self, leaf_id):
        leaf_id = ObjectId(leaf_id)

        if leaf_id in self.application.branch.leaves:
            leaf = self.application.branch.leaves[leaf_id]
            self.application.branch.del_leaf(leaf)

        self.finish()
