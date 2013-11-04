# -*- coding: utf-8 -*-

from __future__ import print_function
import MySQLdb
import string
import random
import simplejson as json
import tornado.web
import pymongo
from components.shadow import encode, decode


class Roots(tornado.web.RequestHandler):
    def get(self):
        self.write("Hello to you from roots!")

    def post(self):
        response = ""
        message = None
        try:
            message = json.loads(decode(self.get_argument('message', None), self.application.settings["secret"]))
        except:
            self.write(json.dumps({
                "result": "failure",
                "message": "failed to decode message"
            }))
            return
        # Далее message - тело запроса

        function = message.get('function', None)
        if function == "prepare_database":
            response = self.prepare_database(message)

        # TODO: зашифровать ответ
        self.write(response)

    @staticmethod
    def string_generator(size=16, chars=string.ascii_uppercase + string.digits):
        return ''.join(random.choice(chars) for _ in range(size))

    def mysql_user_exists(self, username):
        db = MySQLdb.connect(
            host=self.application.settings["mysql_host"],
            port=self.application.settings["mysql_port"],
            user=self.application.settings["mysql_user"],
            passwd=self.application.settings["mysql_pass"]
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
            host=self.application.settings["mysql_host"],
            port=self.application.settings["mysql_port"],
            user=self.application.settings["mysql_user"],
            passwd=self.application.settings["mysql_pass"]
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

        print("Preparing database for {0}".format(name))
        client = pymongo.MongoClient(
            self.application.settings["mongo_host"],
            self.application.settings["mongo_port"]
        )
        leaves = client.roots.leaves
        leaf = leaves.find_one({"name": name})
        if leaf:
            print("Found existing database")
            result = {
                "result": "success",
                "env":
                {
                    "db_host": self.application.settings["mysql_host"],
                    "db_port": self.application.settings["mysql_port"],
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
                "db_host": self.application.settings["mysql_host"],
                "db_port": self.application.settings["mysql_port"],
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

        print("No existing database; creating new called {0}".format(db_name))

        db = MySQLdb.connect(
            host=self.application.settings["mysql_host"],
            port=self.application.settings["mysql_port"],
            user=self.application.settings["mysql_user"],
            passwd=self.application.settings["mysql_pass"]
        )
        cur = db.cursor()
        cur.execute("CREATE DATABASE `{0}` CHARACTER SET utf8 COLLATE "
                    "utf8_general_ci".format(db_name))
        cur.execute("CREATE USER '{0}'@'localhost' IDENTIFIED BY '{1}'".format(username, password))
        cur.execute("GRANT ALL PRIVILEGES ON {0}.* TO '{1}'@'localhost' WITH GRANT"
                    " OPTION".format(db_name, username))
        db.close()
        return json.dumps(result)

    def delete_database(self):
        name = self.get_argument("name", None)
        if not name:
            return json.dumps({
                "result": "failure",
                "message": "missing argument: name"
            })
        # TODO: Удаление самой базы и инстанса по имени из сохраненных
        pass