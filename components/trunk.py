# -*- coding: utf-8 -*-
import traceback
import os

import pymongo
import simplejson as json
from tornado import template
from tornado.gen import coroutine, Return
import tornado.httpclient
import tornado.template
import tornado.web
from pbkdf2 import crypt

from components.common import LogicError
from components.database import get_default_database, get_settings_connection


class Trunk(tornado.web.Application):
    def __init__(self, settings_dict, **settings):
        super(Trunk, self).__init__(**settings)
        self.settings = settings_dict
        self.settings["cookie_secret"] = "asdasd"

        # Компоненты
        self.branch = None
        self.air = None
        self.roots = None
        self.druid = None

        self.loader = template.Loader(os.path.join(self.settings["REALPATH"], "html"))

        self.initial_publish()

    def initial_publish(self):
        trunk = get_default_database(self.settings)
        instance = trunk.components.find_one({"name": self.settings["name"]})

        if not instance:
            about = {
                "name": self.settings["name"],
                "host": self.settings["trunk_host"],
                "port": self.settings["trunk_port"],
                "roles": {}
            }
            instance = trunk.components.insert(about)
        self.settings["id"] = instance.get("_id")

    def publish_self(self):
        trunk = get_default_database(self.settings)
        instance = trunk.components.find_one({"name": self.settings["name"]})

        about = {
            "name": self.settings["name"],
            "host": self.settings["trunk_host"],
            "port": self.settings["trunk_port"],
            "roles": {}
        }
        if self.branch:
            about["roles"]["branch"] = self.branch.settings
        if self.air:
            about["roles"]["air"] = self.air.settings
        if self.roots:
            about["roles"]["roots"] = self.roots.settings

        if not instance:
            trunk.components.insert(about)

        trunk.components.update({"name": self.settings["name"]}, about)

    @coroutine
    def authenticate_user(self, username, password):
        db = get_default_database(self.settings, async=True)
        try:
            user = yield db.user.find_one({"username": username})
            assert crypt(password, user.get("password"))
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
