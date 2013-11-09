# -*- coding: utf-8 -*-
from __future__ import print_function
import MySQLdb
import string
import random
import simplejson as json
import tornado.web
import pymongo
from components.shadow import encode, decode
from components.common import log_message


class Roots(tornado.web.Application):
    def __init__(self, settings_dict, **settings):
        super(Roots, self).__init__(**settings)
        self.settings = settings_dict

    def process_message(self, message):
        function = message.get('function', None)
        if function == "prepare_database":
            response = self.prepare_database(message)
        if function == "status_report":
            response = self.status_report()

        if function is None:
            response = json.dumps({
                "result": "failure",
                "message": "No function or unknown one called"
            })
        return response

    def status_report(self):
        return json.dumps({
            "result": "success",
            "message": "Working well",
            "role": "roots"
        })
    @staticmethod
    def string_generator(size=8, chars=string.ascii_uppercase + string.digits):
        return ''.join(random.choice(chars) for _ in range(size))

    def mysql_user_exists(self, username):
        db = MySQLdb.connect(
            host=self.settings["mysql_host"],
            port=self.settings["mysql_port"],
            user=self.settings["mysql_user"],
            passwd=self.settings["mysql_pass"]
        )
        cur = db.cursor()
        cur.execute("SELECT EXISTS(SELECT 1 FROM mysql.user WHERE user = '{0}')".format(username))
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
            host=self.settings["mysql_host"],
            port=self.settings["mysql_port"],
            user=self.settings["mysql_user"],
            passwd=self.settings["mysql_pass"]
        )
        cur = db.cursor()
        cur.execute("SELECT EXISTS(SELECT 1 FROM INFORMATION_SCHEMA.SCHEMATA WHERE"
                    " SCHEMA_NAME = '{0}')".format(dbname))
        result = cur.fetchall()
        cur.close()
        return bool(result[0][0])

    def prepare_database(self, message):
        name = message.get("name", None)
        if not name:
            return json.dumps({
                "result": "failure",
                "message": "missing argument: name"
            })

        log_message("Preparing database for {0}".format(name))
        client = pymongo.MongoClient(
            self.settings["mongo_host"],
            self.settings["mongo_port"]
        )
        leaves = client.roots.leaves
        leaf = leaves.find_one({"name": name})
        if leaf:
            log_message("Found existing database {0} for leaf {1}".format(leaf["db_name"], name))
            result = {
                "result": "success",
                "env":
                {
                    "db_host": self.settings["mysql_host"],
                    "db_port": self.settings["mysql_port"],
                    "db_name": leaf["db_name"],
                    "db_user": leaf["db_user"],
                    "db_pass": leaf["db_pass"]
                }
            }
            return json.dumps(result)

        db_name = name
        if self.mysql_db_exists(db_name):
            db_name = self.string_generator()

        username = self.generate_username()
        password = self.string_generator()
        result = {
            "result": "success",
            "env":
            {
                "db_host": self.settings["mysql_host"],
                "db_port": self.settings["mysql_port"],
                "db_name": db_name,
                "db_user": username,
                "db_pass": password
            }
        }

        leaf = {
            "name": name,
            "db_name": db_name,
            "db_user": username,
            "db_pass": password
        }
        leaves.insert(leaf)

        log_message("No existing database; creating new called {0}".format(db_name))

        db = MySQLdb.connect(
            host=self.settings["mysql_host"],
            port=self.settings["mysql_port"],
            user=self.settings["mysql_user"],
            passwd=self.settings["mysql_pass"]
        )
        try:
            cur = db.cursor()
            cur.execute("CREATE DATABASE `{0}` CHARACTER SET utf8 COLLATE "
                        "utf8_general_ci".format(db_name))
            cur.execute("CREATE USER '{0}'@'%' IDENTIFIED BY '{1}'".format(username, password))
            cur.execute("GRANT ALL PRIVILEGES ON {0}.* TO '{1}'@'%' WITH GRANT"
                        " OPTION".format(db_name, username))
            cur.execute("FLUSH PRIVILEGES;")
            db.close()
        except Exception, e:
            result = {
                "result": "failure",
                "message": e.message
            }
        return json.dumps(result)

    def delete_database(self, message):
        name = message.get("name", None)
        if not name:
            return json.dumps({
                "result": "failure",
                "message": "missing argument: name"
            })
        # TODO: Удаление самой базы и инстанса по имени из сохраненных
        pass