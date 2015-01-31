# -*- coding: utf-8 -*-
from __future__ import print_function, unicode_literals

from components.batteries import Mongo, MySQL
from components.common import log_message
from tornado.gen import Return, coroutine
import simplejson as json
from bson import json_util

import os


class Roots():

    def __init__(self, trunk, settings):
        self.settings = settings
        self.trunk = trunk

        self.__roots_dir__ = self.settings.get("roots_dir") or os.path.join(self.trunk.forest_root, "roots")
        log_message("Started roots", component="Roots")

        self.batteries_mysql = {}
        self.batteries_mongo = {}

    @property
    def root(self):
        return self.__roots_dir__

    @property
    def metaroot(self):
        return os.path.join(self.root, "meta")

    @property
    def dataroot(self):
        return os.path.join(self.root, "data")

    @coroutine
    def initialize(self):
        for f in os.listdir(self.metaroot):
            if not os.path.isfile(os.path.join(self.metaroot, f)):
                continue

            name, ext = os.path.splitext(f)

            if ext == "mysql":
                with open(os.path.join(self.metaroot, f)) as config:
                    config = json.load(f.read(), object_hook=json_util.object_hook)

                    self.batteries_mysql[config["owner"]] = MySQL(**config)
                    yield self.batteries_mysql[config["owner"]].start()

    def save_config(self, battery):
        cfg_name = "{}.{}".format(battery.owner, battery.config_ext)

        with open(os.path.join(self.metaroot, cfg_name), "w") as config:
            config.write(json.dumps(battery.config), default=json_util.default, indent=2)

    def cleanup(self):
        for key, value in self.batteries_mysql.items():
            value.stop()

    @coroutine
    def create_db(self, name, db_type):
        credentials = {}
        if "mysql" in db_type:
            credentials["mysql"] = yield MySQL(self.settings["mysql"], self.trunk).prepare_leaf(name)
        raise Return(credentials)
