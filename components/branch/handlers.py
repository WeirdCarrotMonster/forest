# coding=utf-8

from __future__ import unicode_literals
import tornado.web
import tornado.gen
import simplejson as json
from components.api.decorators import token_auth
from bson import ObjectId, json_util


class LeavesHandler(tornado.web.RequestHandler):

    """
    Выполняет управление каждым отдельно взятым листом
    """
    @tornado.gen.coroutine
    @token_auth
    def get(self):
        """
        Возвращает список всех известных листьев
        """
        pass

    @tornado.gen.coroutine
    @token_auth
    def post(self):
        data = json.loads(self.request.body, object_hook=json_util.object_hook)

        leaf = yield self.application.branch.create_leaf(data)

        if leaf:
            started = self.application.branch.add_leaf(leaf)
            self.finish(json.dumps({"result": "started" if started else "queued"}))
        else:
            self.set_status(400)
            self.finish(json.dumps({"result": "error", "message": "Unknown species"}))


class LeafHandler(tornado.web.RequestHandler):

    """
    Выполняет управление каждым отдельно взятым листом
    """
    @tornado.gen.coroutine
    @token_auth
    def get(self, _id):
        """
        Получает информацию о листе с указанным id
        """
        self.finish(json.dumps(self.application.emperor.stats(_id)))

    @tornado.gen.coroutine
    @token_auth
    def post(self):
        """
        Перезаписывает настройки листа
        """
        pass

    @tornado.gen.coroutine
    @token_auth
    def delete(self, leaf_id):
        leaf_id = ObjectId(leaf_id)

        if leaf_id in self.application.branch.leaves:
            leaf = self.application.branch.leaves[leaf_id]
            self.application.branch.del_leaf(leaf)

        self.finish()


class SpeciesListHandler(tornado.web.RequestHandler):

    @tornado.gen.coroutine
    @token_auth
    def post(self):
        data = json.loads(self.request.body, object_hook=json_util.object_hook)

        self.application.branch.create_species(data)

        self.finish(json.dumps({"result": "success", "message": "OK"}))


class SpeciesHandler(tornado.web.RequestHandler):

    @tornado.gen.coroutine
    @token_auth
    def get(self, _id):
        _id = ObjectId(_id)

        species = self.application.branch.get_species(_id)

        if species:
            self.finish(json.dumps({}))
        else:
            self.set_status(404)
            self.finish()

    @tornado.gen.coroutine
    @token_auth
    def patch(self, _id):
        data = json.loads(self.request.body, object_hook=json_util.object_hook)

        self.application.branch.create_species(data)

        self.finish(json.dumps({"result": "success", "message": "OK"}))


class LoggerListHandler(tornado.web.RequestHandler):

    @tornado.gen.coroutine
    @token_auth
    def get(self):
        self.finish(json.dumps([
            {
                "identifier": logger.identifier,
                "type": logger.__class__.__name__
            } for logger in self.application.branch.__loggers__
        ]))

    @tornado.gen.coroutine
    @token_auth
    def post(self):
        data = json.loads(self.request.body, object_hook=json_util.object_hook)

        result, message = self.application.branch.add_logger(data)
        if not result:
            self.set_status(400)
            self.finish(json.dumps({"result": "failure", "message": message}))
        else:
            self.finish(json.dumps({"result": "success"}))


class LoggerHandler(tornado.web.RequestHandler):

    @tornado.gen.coroutine
    @token_auth
    def delete(self, identifier):
        result, code, message = self.application.branch.delete_logger(identifier)
        if not result:
            self.set_status(code)
            self.finish(json.dumps({"result": "failure", "message": message}))
        else:
            self.finish(json.dumps({"result": "success"}))
