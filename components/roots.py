# -*- coding: utf-8 -*-
from __future__ import print_function
import MySQLdb
import string
import random
from components.common import log_message, get_default_database


class Roots():

    def __init__(self, settings):
        self.settings = settings
        self.update_state()

        self.functions = {
            "roots.update_state": self.update_state
        }

    @staticmethod
    def string_generator(size=8, chars=string.ascii_uppercase + string.digits):
        return ''.join(random.choice(chars) for _ in range(size))

    def mysql_user_exists(self, username):
        db = MySQLdb.connect(
            host=self.settings.get("mysql_inner", "127.0.0.1"),
            port=self.settings["mysql_port"],
            user=self.settings["mysql_user"],
            passwd=self.settings["mysql_pass"]
        )
        cur = db.cursor()
        cur.execute(
            "SELECT EXISTS(SELECT 1 FROM mysql.user \
                WHERE user = '{0}')".format(username))
        result = cur.fetchall()
        cur.close()
        return bool(result[0][0])

    def generate_username(self):
        username = self.string_generator()
        while self.mysql_user_exists(username):
            username = self.string_generator()
        return username

    def mysql_db_exists(self, dbname):
        db = MySQLdb.connect(
            host=self.settings.get("mysql_inner", "127.0.0.1"),
            port=self.settings["mysql_port"],
            user=self.settings["mysql_user"],
            passwd=self.settings["mysql_pass"]
        )
        cur = db.cursor()
        cur.execute("SELECT EXISTS(SELECT 1 FROM INFORMATION_SCHEMA.SCHEMATA "
                    "WHERE SCHEMA_NAME = '{0}')".format(dbname))
        result = cur.fetchall()
        cur.close()
        return bool(result[0][0])

    def update_state(self, **kwargs):
        trunk = get_default_database(self.settings)
        to_prepare = trunk.leaves.find({"env": {'$exists': False}})
        for leaf in to_prepare:
            env = self.prepare_database(leaf["name"])
            if env:
                trunk.leaves.update(
                    {"name": leaf["name"]},
                    {"$set": {"env": env}}
                )

        return {
            "result": "success"
        }

    def prepare_database(self, name):
        log_message(
            "Preparing database for {0}".format(name),
            component="Roots"
        )

        db_name = name
        if self.mysql_db_exists(db_name):
            db_name = self.string_generator()

        username = self.generate_username()
        password = self.string_generator()
        result = {
            "db_host": self.settings["mysql_host"],
            "db_port": self.settings["mysql_port"],
            "db_name": db_name,
            "db_user": username,
            "db_pass": password
        }

        log_message(
            "Creating database {0}".format(db_name),
            component="Roots"
        )

        db = MySQLdb.connect(
            host=self.settings.get("mysql_inner", "127.0.0.1"),
            port=self.settings["mysql_port"],
            user=self.settings["mysql_user"],
            passwd=self.settings["mysql_pass"]
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
