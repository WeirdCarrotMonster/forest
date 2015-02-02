# -*- coding: utf-8 -*-

from __future__ import unicode_literals, print_function

from tornado.gen import coroutine, Return, Task

from tornado.ioloop import IOLoop

from components.emperor import Vassal
from components.common import log_message
from components.cmdrunner import call_subprocess
from components.database import get_settings_connection_async


import random
import string

import pymysql
from pymysql import OperationalError
import os
import time

try:
    from subprocess import DEVNULL
except ImportError:
    DEVNULL = open(os.devnull, 'wb')


class Battery(Vassal):

    def __init__(
            self,
            path=None,
            port=None,
            owner=None,
            rootpass=None,
            username=None,
            password=None,
            database=None,
            **kwargs):
        super(Battery, self).__init__(**kwargs)
        self.__path__ = path
        self.__port__ = port
        self.__owner__ = owner
        self.__rootpass__ = rootpass or self.string_generator()
        self.__username__ = username or self.string_generator()
        self.__password__ = password or self.string_generator()
        self.__database__ = database or self.string_generator()

    @staticmethod
    def string_generator(size=8, chars=string.ascii_uppercase + string.digits):
        return ''.join(random.choice(chars) for _ in range(size))

    @property
    def owner(self):
        return self.__owner__

    @property
    def config(self):
        return {
            "path": self.__path__,
            "port": self.__port__,
            "owner": self.__owner__,
            "rootpass": self.__rootpass__,
            "username": self.__username__,
            "password": self.__password__,
            "database": self.__database__
        }

    @property
    def config_ext(self):
        raise NotImplementedError

    @coroutine
    def wait(self):
        raise NotImplementedError


class MySQL(Battery):

    def __init__(self, **kwargs):
        super(MySQL, self).__init__(**kwargs)
        self.__server__ = None

    @property
    def config_ext(self):
        return "mysql"

    @coroutine
    def initialize(self):
        if not os.path.exists(self.__path__):
            log_message("Initializing database directory")
            os.makedirs(self.__path__)
            result, error = yield call_subprocess(
                [
                    "mysql_install_db",
                    "--no-defaults",
                    "--datadir={}".format(self.__path__),
                    "--basedir=/usr"
                ]
            )

            with open(os.path.join(self.__path__, "firstrun.sql"), "w") as config:
                config.write("""
DELETE FROM mysql.user;
CREATE USER 'root'@'%' IDENTIFIED BY '{0}';
GRANT ALL ON *.* TO 'root'@'%' WITH GRANT OPTION;
DROP DATABASE IF EXISTS test;
CREATE DATABASE IF NOT EXISTS `{1}` CHARACTER SET utf8 COLLATE utf8_general_ci;
GRANT ALL PRIVILEGES ON {1}.* TO '{2}'@'%' IDENTIFIED BY '{3}' WITH GRANT OPTION;
FLUSH PRIVILEGES;
""".format(self.__rootpass__, self.__database__, self.__username__, self.__password__)
                )
        else:
            pass

    @coroutine
    def wait(self, timeout=30):
        t = timeout
        while t >= 0:
            t -= 1

            try:
                pymysql.connect(
                    host="127.0.0.1",
                    port=self.__port__
                )
                raise Return(True)
            except OperationalError as e:
                if "Access denied for user" in e.args[1]:
                    raise Return(True)

            yield Task(IOLoop.current().add_timeout, time.time() + 1)

        raise Return(False)

    def __get_config__(self):
        return """[uwsgi]
master=true
attach-daemon=mysqld --no-defaults --datadir={0} --port={1} --socket={0}/socket --skip-name-resolve --init-file={0}/firstrun.sql
""".format(self.__path__, self.__port__)


class Mongo(Battery):

    def __init__(self, settings, trunk):
        Battery.__init__(self)
        self.settings = settings
        self.trunk = trunk

    @coroutine
    def prepare_leaf(self, name):
        log_message(
            "Preparing Mongo for {0}".format(name),
            component="Roots"
        )

        self.settings["database"] = "admin"
        con = get_settings_connection_async(self.settings)

        db_names = yield con.database_names()

        while name in db_names:
            name = Mongo.string_generator()

        db = con[name]

        username = Mongo.string_generator()
        password = Mongo.string_generator()

        yield db.add_user(username, password, roles=["readWrite"])

        raise Return({
            "name": name,
            "user": username,
            "pass": password,
            "host": self.settings.get("host", "127.0.0.1"),
            "port": self.settings["port"]
        })

    @staticmethod
    def string_generator(size=8, chars=string.ascii_uppercase + string.digits):
        return ''.join(random.choice(chars) for _ in range(size))
