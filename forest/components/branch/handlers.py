# coding=utf-8

from __future__ import unicode_literals
from bson import ObjectId

import tornado.web
import tornado.gen

from forest.components.species import Species
from forest.components.common import loads, dumps
from forest.components.api.decorators import token_auth
from forest.components.exceptions.logger import LoggerCreationError


# pylint: disable=W0221,W0613


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
        self.write("[")

        first = True
        for leaf in self.application.branch.leaves.keys():
            if not first:
                self.write(",")
            else:
                first = False

            self.write(dumps(leaf))

        self.finish("]")

    @tornado.gen.coroutine
    @token_auth
    def post(self):
        data = loads(self.request.body)

        try:
            leaf = self.application.branch.create_leaf(data)
            started = self.application.branch.add_leaf(leaf)
            self.finish(dumps({"result": "started" if started else "queued"}))
        except Species.NotDefined:
            self.set_status(400)
            self.finish(dumps({"result": "error", "message": "Unknown species"}))


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
        self.finish(dumps(self.application.emperor.stats(_id)))

    @tornado.gen.coroutine
    @token_auth
    def delete(self, leaf_id):
        leaf_id = ObjectId(leaf_id)

        if leaf_id in self.application.branch.leaves:
            leaf = self.application.branch.leaves[leaf_id]
            self.application.branch.del_leaf(leaf)

        self.finish()


class LeafRPCHandler(tornado.web.RequestHandler):

    @tornado.gen.coroutine
    @token_auth
    def post(self, _id):
        data = loads(self.request.body)
        assert type(data) == list

        response = yield self.application.emperor.call_vassal_rpc(_id, *data)

        self.finish(dumps(response))


class SpeciesListHandler(tornado.web.RequestHandler):

    @tornado.gen.coroutine
    @token_auth
    def post(self):
        data = loads(self.request.body)

        yield self.application.branch.create_species(data)

        self.finish(dumps({"result": "success", "message": "OK"}))


class SpeciesHandler(tornado.web.RequestHandler):

    @tornado.gen.coroutine
    @token_auth
    def get(self, _id):
        _id = ObjectId(_id)

        species = self.application.branch.species.get(_id)

        if species:
            self.finish(dumps(species.description))
        else:
            self.set_status(404)
            self.finish(dumps({}))

    @tornado.gen.coroutine
    @token_auth
    def patch(self, _id):
        data = loads(self.request.body)

        self.application.branch.create_species(data)

        self.finish(dumps({"result": "success", "message": "OK"}))


class LoggerListHandler(tornado.web.RequestHandler):

    @tornado.gen.coroutine
    @token_auth
    def get(self):
        self.finish(dumps([
            {
                "identifier": logger.identifier,
                "type": logger.__class__.__name__
            } for logger in self.application.branch.__loggers__
        ]))

    @tornado.gen.coroutine
    @token_auth
    def post(self):
        data = loads(self.request.body)

        try:
            self.application.branch.add_logger(data)
            self.finish(dumps({"result": "success"}))
        except LoggerCreationError as e:
            self.set_status(400)
            self.finish(dumps({"result": "failure", "message": e.message}))


class LoggerHandler(tornado.web.RequestHandler):

    @tornado.gen.coroutine
    @token_auth
    def delete(self, identifier):
        result, code, message = self.application.branch.delete_logger(identifier)
        if not result:
            self.set_status(code)
            self.finish(dumps({"result": "failure", "message": message}))
        else:
            self.finish(dumps({"result": "success"}))
