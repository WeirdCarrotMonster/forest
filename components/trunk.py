# -*- coding: utf-8 -*-
from bson import ObjectId

from tornado.gen import coroutine, Return
import tornado.httpclient
import tornado.template
import tornado.web
from pbkdf2 import crypt

from components.database import get_default_database


class Trunk(tornado.web.Application):
    def __init__(self, settings_dict, **settings):
        super(Trunk, self).__init__(**settings)
        self.settings["cookie_secret"] = "asdasd"
        self.database = settings_dict["db"]
        self.name = settings_dict["name"]

        self.async_db = get_default_database(self.database, async=True)
        self.sync_db = get_default_database(self.database)

        self.branch = None
        self.roots = None
        self.druid = None
        self.air = None
        self.root = settings_dict["root"]

    @property
    def id(self):
        return self.name

    @property
    def forest_root(self):
        return self.root

    @coroutine
    def authenticate_user(self, username, password):
        try:
            user = yield self.async_db.user.find_one({"username": username})
            assert user.get("password") == crypt(password, user.get("password"))
            raise Return(user)
        except Return as r:
            raise r
        except Exception as e:
            print(e)
            raise Return(None)

    def cleanup(self):
        if self.branch:
            self.branch.cleanup()
        if self.air:
            self.air.cleanup()
