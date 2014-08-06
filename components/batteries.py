# -*- coding: utf-8 -*-

from __future__ import unicode_literals
from components.common import log_message
from components.database import get_default_database, get_settings_connection
import string
import random
import MySQLdb


class Battery(object):
    def __init__(self):
        pass

    @staticmethod
    def prepare(settings):
        raise NotImplemented


class MySQL(Battery):
    def __init__(self):
        Battery.__init__(self)

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

    @staticmethod
    def prepare_database(settings, name):
        log_message(
            "Preparing MySQL for {0}".format(name),
            component="Roots"
        )

        db_name = name
        if MySQL.mysql_db_exists(settings, db_name):
            db_name = MySQL.string_generator()

        username = MySQL.generate_username(settings)
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
            host=settings.get("host", "127.0.0.1"),
            port=settings["port"],
            user=settings["user"],
            passwd=settings["pass"]
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
        return result

    @staticmethod
    def prepare(settings, trunk):
        species = [s["name"] for s in trunk.species.find({"requires": "mysql"})]

        to_prepare = trunk.leaves.find({
            "type": {"$in": species},
            "batteries.mysql": {'$exists': False}
        })
        for leaf in to_prepare:
            env = MySQL.prepare_database(settings, leaf["name"])
            if env:
                trunk.leaves.update(
                    {"name": leaf["name"]},
                    {
                        "$set": {"batteries.mysql": env}
                    }
                )


class Mongo(Battery):
    def __init__(self):
        Battery.__init__(self)

    @staticmethod
    def string_generator(size=8, chars=string.ascii_uppercase + string.digits):
        return ''.join(random.choice(chars) for _ in range(size))

    @staticmethod
    def prepare_database(settings, name):
        log_message(
            "Preparing MongoDB for {0}".format(name),
            component="Roots"
        )
        con = get_settings_connection(settings)
        while name in con.database_names():
            name = Mongo.string_generator()

        db = con[name]

        username = Mongo.string_generator()
        password = Mongo.string_generator()

        db.add_user(username, password, roles=["readWrite"])

        return {
            "name": name,
            "user": username,
            "pass": password
        }

    @staticmethod
    def prepare(settings, trunk):
        species = [s["name"] for s in trunk.species.find({"requires": "mongo"})]

        to_prepare = trunk.leaves.find({
            "type": {"$in": species},
            "batteries.mongo": {'$exists': False}
        })

        for leaf in to_prepare:
            env = Mongo.prepare_database(settings, leaf["name"])
            if env:
                trunk.leaves.update(
                    {"name": leaf["name"]},
                    {"$set": {
                        "batteries.mongo": env}
                    }
                )
