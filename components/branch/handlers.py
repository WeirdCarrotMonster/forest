#coding=utf-8

from __future__ import unicode_literals
import tornado.web
import tornado.gen


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
