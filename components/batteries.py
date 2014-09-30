# -*- coding: utf-8 -*-

from __future__ import unicode_literals

import random
import string

import MySQLdb
from tornado.gen import coroutine

from components.common import log_message
from components.database import get_default_database, get_settings_connection_async


class Battery(object):
    def __init__(self):
        pass

    def update(self):
        raise NotImplemented


class MySQL(Battery):
    def __init__(self, settings, trunk):
        Battery.__init__(self)
        self.settings = settings
        self.trunk = trunk

        cursor = self.trunk.species.find({"requires": "mysql"})
        cursor.each(callback=self.add_specie)

        self.species = []

    def add_specie(self, result, error):
        if not result:
            return

        self.species.append(result["_id"])

    @staticmethod
    def string_generator(size=8, chars=string.ascii_uppercase + string.digits):
        return ''.join(random.choice(chars) for _ in range(size))

    @staticmethod
    def mysql_user_exists(settings, username):
        db = MySQLdb.connect(
            host=settings.get("host", "127.0.0.1"),
            port=settings["port"],
            user=settings["user"],
            passwd=settings["pass"]
        )
        cur = db.cursor()
        cur.execute(
            "SELECT EXISTS(SELECT 1 FROM mysql.user WHERE user = '{0}')".format(username))
        result = cur.fetchall()
        cur.close()
        return bool(result[0][0])

    @staticmethod
    def mysql_db_exists(settings, db_name):
        db = MySQLdb.connect(
            host=settings.get("host", "127.0.0.1"),
            port=settings["port"],
            user=settings["user"],
            passwd=settings["pass"]
        )
        cur = db.cursor()
        cur.execute("SELECT EXISTS(SELECT 1 FROM INFORMATION_SCHEMA.SCHEMATA "
                    "WHERE SCHEMA_NAME = '{0}')".format(db_name))
        result = cur.fetchall()
        cur.close()
        return bool(result[0][0])

    @staticmethod
    def generate_username(settings):
        username = MySQL.string_generator()
        while MySQL.mysql_user_exists(settings, username):
            username = MySQL.string_generator()
        return username

    @coroutine
    def prepare_leaf(self, leaf, error):
        if not leaf:
            return

        log_message(
            "Preparing MySQL for {0}".format(leaf["name"]),
            component="Roots"
        )

        db_name = leaf["name"]
        if MySQL.mysql_db_exists(self.settings, db_name):
            db_name = MySQL.string_generator()

        username = MySQL.generate_username(self.settings)
        password = MySQL.string_generator()
        result = {
            "name": db_name,
            "user": username,
            "pass": password
        }

        log_message(
            "Creating database {0}".format(db_name),
            component="Roots"
        )

        db = MySQLdb.connect(
            host=self.settings.get("host", "127.0.0.1"),
            port=self.settings["port"],
            user=self.settings["user"],
            passwd=self.settings["pass"]
        )
        try:
            cur = db.cursor()
            cur.execute(
                """
                CREATE DATABASE `{0}` CHARACTER SET utf8
                COLLATE utf8_general_ci;
                GRANT ALL PRIVILEGES ON {0}.* TO '{1}'@'%'
                IDENTIFIED BY '{2}' WITH GRANT OPTION;
                FLUSH PRIVILEGES;
                """.format(db_name, username, password)
            )
            db.close()
        except:
            result = None

        yield self.trunk.leaves.update(
            {"_id": leaf["_id"]},
            {
                "$set": {"batteries.mysql": result}
            }
        )

    def update(self):
        cursor = self.trunk.leaves.find({
            "type": {"$in": self.species},
            "batteries.mysql": {'$exists': False}
        })

        cursor.each(callback=self.prepare_leaf)


class Mongo(Battery):
    def __init__(self, settings, trunk):
        Battery.__init__(self)
        self.settings = settings
        self.trunk = trunk

        self.last_update = None

        cursor = self.trunk.species.find({"requires": "mongo"})
        cursor.each(callback=self.add_specie)

        self.species = []

    def add_specie(self, result, error):
        if not result:
            return

        self.species.append(result["_id"])

    @coroutine
    def update(self):
        trunk = get_default_database(self.settings, async=True)
        query = {
            "type": {"$in": self.species},
            "batteries.mongo": {'$exists': False}
        }

        cursor = trunk.leaves.find(query)
        cursor.each(callback=self.prepare_leaf)

    @coroutine
    def prepare_leaf(self, leaf, error):
        if not leaf:
            return

        log_message(
            "Preparing Mongo for {0}".format(leaf["name"]),
            component="Roots"
        )

        name = leaf["name"]

        con = get_settings_connection_async(self.settings)

        db_names = yield con.database_names()
        while name in db_names:
            name = Mongo.string_generator()

        db = con[name]

        username = Mongo.string_generator()
        password = Mongo.string_generator()

        yield db.add_user(username, password, roles=["readWrite"])

        yield con.trunk.leaves.update(
            {"_id": leaf["_id"]},
            {"$set": {
                "batteries.mongo": {
                    "name": name,
                    "user": username,
                    "pass": password
                }
            }
            }
        )


    @staticmethod
    def string_generator(size=8, chars=string.ascii_uppercase + string.digits):
        return ''.join(random.choice(chars) for _ in range(size))