# -*- coding: utf-8 -*-
from __future__ import print_function, unicode_literals

from tornado.gen import Return, coroutine

from forest.components.roots.batteries import Mongo, MySQL
from forest.components.common import log_message


# pylint: disable=W0612,W0613


class Roots(object):

    def __init__(self, trunk, settings):
        self.settings = settings
        self.trunk = trunk
        self.__mongo_settings__ = self.settings.get("mongo", {})
        self.__mysql_settings__ = self.settings.get("mysql", {})

        log_message("Started roots", component="Roots")

    def __get_mongo__(self, name):
        return Mongo(
            owner=str(name),
            port=27017,
            rootpass=self.__mongo_settings__.get("rootpass", "password"),
            database=str(name)
        )

    def __get_mysql__(self, name):
        return MySQL(
            owner=str(name),
            port=3306,
            rootpass=self.__mysql_settings__.get("rootpass", "password"),
            database=str(name)
        )

    @coroutine
    def create_db(self, _id, db_type):
        credentials = {}
        if "mysql" in db_type:
            log_message("Creating mysql for {}".format(_id), component="Roots")
            db = self.__get_mysql__(_id)
            yield db.initialize()
            credentials["mysql"] = {
                "host": self.trunk.host,
                "port": db.__port__,
                "name": db.__database__,
                "user": db.__username__,
                "pass": db.__password__
            }
        if "mongo" in db_type:
            log_message("Creating mongodb for {}".format(_id), component="Roots")
            db = self.__get_mongo__(_id)
            yield db.initialize()
            credentials["mongo"] = {
                "host": self.trunk.host,
                "port": db.__port__,
                "name": db.__database__,
                "user": db.__username__,
                "pass": db.__password__
            }
        raise Return(credentials)
