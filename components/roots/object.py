# -*- coding: utf-8 -*-
from __future__ import print_function, unicode_literals

import os

from tornado.gen import Return, coroutine
import simplejson as json
from bson import json_util

from components.batteries import MySQL, Mongo, MongoShared
from components.common import log_message


class Roots():

    def __init__(self, trunk, settings):
        self.settings = settings
        self.trunk = trunk

        self.__roots_dir__ = self.settings.get("roots_dir") or os.path.join(self.trunk.forest_root, "roots")
        log_message("Started roots", component="Roots")

        self.batteries_mysql = {}
        self.batteries_mongo = {}
        self.port_range = set(range(30000, 35000))

        self.initialize()

    @property
    def root(self):
        return self.__roots_dir__

    @property
    def metaroot(self):
        return os.path.join(self.root, "meta")

    @property
    def dataroot(self):
        return os.path.join(self.root, "data")

    def initialize(self):
        for f in os.listdir(self.metaroot):
            if not os.path.isfile(os.path.join(self.metaroot, f)):
                continue

            name, ext = os.path.splitext(f)

            with open(os.path.join(self.metaroot, f)) as config:
                config = json.load(config, object_hook=json_util.object_hook)
                if not "username" and "password" and "rootpass" and "database" and "path" and "port" and "owner" in config:
                    log_message("Malformed config for {name}{ext}, skipping".format(**locals()))
                    continue

                if ext == ".mysql":
                    log_message("Starting mysql server for {}".format(config["owner"]), component="Roots")

                    self.port_range -= {config["port"]}

                    self.batteries_mysql[config["owner"]] = MySQL(emperor=self.trunk.emperor, **config)
                    self.batteries_mysql[config["owner"]].start()

                if ext == ".mongo":
                    log_message("Starting mongo server for {}".format(config["owner"]), component="Roots")

                    self.port_range -= {config["port"]}

                    self.batteries_mongo[config["owner"]] = Mongo(emperor=self.trunk.emperor, **config)
                    self.batteries_mongo[config["owner"]].start()

    def save_config(self, battery):
        cfg_name = "{}.{}".format(battery.owner, battery.config_ext)

        with open(os.path.join(self.metaroot, cfg_name), "w") as config:
            config.write(
                json.dumps(battery.config, default=json_util.default, indent=2)
            )

    def cleanup(self):
        for key, value in self.batteries_mysql.items():
            value.stop()
        for key, value in self.batteries_mongo.items():
            value.stop()

    def __get_mongo__(self, name):
        if True:
            return Mongo(
                emperor=self.trunk.emperor,
                owner=str(name),
                port=self.port_range.pop(),
                path=os.path.join(self.dataroot, "{}_mongo".format(name))
            )
        else:
            return MongoShared(
                owner=str(name),
                rootpass=None,
                database=name
            )

    @coroutine
    def create_db(self, _id, db_type):
        credentials = {}
        if "mysql" in db_type:
            log_message("Creating mysql for {}".format(_id), component="Roots")
            db = MySQL(
                emperor=self.trunk.emperor,
                owner=str(_id),
                port=self.port_range.pop(),
                path=os.path.join(self.dataroot, "{}_mysql".format(_id))
            )
            self.batteries_mysql[_id] = db
            yield db.initialize()
            db.start()
            self.save_config(db)
            yield db.wait()
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
            self.batteries_mongo[_id] = db
            yield db.initialize()
            db.start()
            self.save_config(db)
            yield db.wait()
            credentials["mongo"] = {
                "host": self.trunk.host,
                "port": db.__port__,
                "name": db.__database__,
                "user": db.__username__,
                "pass": db.__password__
            }
        raise Return(credentials)
