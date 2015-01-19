# -*- coding: utf-8 -*-
import tornado.httpclient
import tornado.template
import tornado.web

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

    def cleanup(self):
        if self.branch:
            self.branch.cleanup()
        if self.air:
            self.air.cleanup()
