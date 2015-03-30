# -*- coding: utf-8 -*-

import os

import tornado.httpclient
import tornado.template
import tornado.web

from forest.components.emperor import Emperor
from forest.components.database import get_default_database


class Trunk(tornado.web.Application):

    def __init__(self, settings_dict, **settings):
        super(Trunk, self).__init__(**settings)
        self.settings["cookie_secret"] = "asdasd"
        self.name = settings_dict["name"]
        self.root = settings_dict["root"]
        self.host = settings_dict["host"]
        self.secret = settings_dict["secret"]
        self.emperor_dir = settings_dict.get("emperor", os.path.join(self.forest_root, "emperor"))

        self.database = settings_dict.get("db")
        if self.database:
            self.async_db = get_default_database(self.database, async=True)
            self.sync_db = get_default_database(self.database)

        self.branch = None
        self.roots = None
        self.druid = None
        self.air = None

        self.emperor = Emperor(self.emperor_dir)

    @property
    def id(self):
        return self.name

    @property
    def forest_root(self):
        return self.root

    def cleanup(self):
        self.emperor.stop()