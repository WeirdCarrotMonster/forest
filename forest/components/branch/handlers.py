# coding=utf-8
"""Хендлеры API сервера приложений."""

from __future__ import unicode_literals

from bson import ObjectId
from forest.components.api.decorators import token_auth
from forest.components.common import loads, dumps
from forest.components.branch.loggers import Logger
from forest.components.species import Species
from tornado import gen, web


# pylint: disable=W0221,W0613


class LeavesHandler(web.RequestHandler):

    """Выполняет управление листом."""

    @gen.coroutine
    @token_auth
    def get(self):
        """Возвращает список всех известных листьев."""
        self.write("[")

        first = True
        for leaf in self.application.branch.leaves.keys():
            if not first:
                self.write(",")
            else:
                first = False

            self.write(dumps(leaf))

        self.finish("]")

    @gen.coroutine
    @token_auth
    def post(self):
        """Создает новый лист."""
        data = loads(self.request.body)

        try:
            leaf = self.application.branch.create_leaf(**data)
            started = self.application.branch.add_leaf(leaf)
            self.finish(dumps({"result": "started" if started else "queued"}))
        except Species.NotDefined:
            self.set_status(400)
            self.finish(dumps({"result": "error", "message": "Unknown species"}))


class LeafHandler(web.RequestHandler):

    """Выполняет управление каждым отдельно взятым листом."""

    @gen.coroutine
    @token_auth
    def get(self, _id):
        """Получает информацию о листе с указанным id."""
        self.finish(dumps(self.application.emperor.stats(_id)))

    @gen.coroutine
    @token_auth
    def delete(self, leaf_id):
        """Останавливает лист."""
        if leaf_id in self.application.branch.leaves:
            leaf = self.application.branch.leaves[leaf_id]
            self.application.branch.del_leaf(leaf)

        self.finish()


class LeafRPCHandler(web.RequestHandler):

    """Выполняет работу с uwsgi-rpc приложения."""

    @gen.coroutine
    @token_auth
    def post(self, _id):
        """Обрабатывает rpc-запрос."""
        data = loads(self.request.body)
        assert type(data) == list

        response = yield self.application.emperor.call_vassal_rpc(_id, *data)

        self.finish(dumps(response))


class SpeciesListHandler(web.RequestHandler):

    """Выполняет работу с видами приложений."""

    @gen.coroutine
    @token_auth
    def post(self):
        """Инициализирует новый вид приложения."""
        data = loads(self.request.body)

        yield self.application.branch.create_species(data)

        self.finish(dumps({"result": "success", "message": "OK"}))


class SpeciesHandler(web.RequestHandler):

    """Выполняет работу с указанным видом приложения."""

    @gen.coroutine
    @token_auth
    def get(self, _id):
        """Возвращает информацию об указанном виде приложения."""
        _id = ObjectId(_id)

        species = self.application.branch.species.get(_id)

        if species:
            self.finish(dumps(species.description))
        else:
            self.set_status(404)
            self.finish(dumps({}))

    @gen.coroutine
    @token_auth
    def patch(self, _id):
        """Модифицирует указанный вид приложения."""
        data = loads(self.request.body)

        self.application.branch.create_species(data)

        self.finish(dumps({"result": "success", "message": "OK"}))


class LoggerListHandler(web.RequestHandler):

    """Выполняет работу с логгерами сервера приложений."""

    @gen.coroutine
    @token_auth
    def get(self):
        """Получает информацию о всех логгерах."""
        self.finish(dumps([
            {
                "identifier": logger.identifier,
                "type": logger.__class__.__name__
            } for logger in self.application.branch.__loggers__
        ]))

    @gen.coroutine
    @token_auth
    def post(self):
        """Создает новый логгер."""
        data = loads(self.request.body)

        try:
            self.application.branch.add_logger(data)
            self.finish(dumps({"result": "success"}))
        except Logger.LoggerCreationError as e:
            self.set_status(400)
            self.finish(dumps({"result": "failure", "message": e.message}))


class LoggerHandler(web.RequestHandler):

    """Выполняет работу с указанным логгером."""

    @gen.coroutine
    @token_auth
    def delete(self, identifier):
        """Удаляет логгер."""
        result, code, message = self.application.branch.delete_logger(identifier)
        if not result:
            self.set_status(code)
            self.finish(dumps({"result": "failure", "message": message}))
        else:
            self.finish(dumps({"result": "success"}))
