# -*- coding: utf-8 -*-

from __future__ import unicode_literals, print_function

import random
import string
import os
import time
import subprocess

from tornado.gen import coroutine, Return, Task
from tornado.ioloop import IOLoop
import pymysql
import motor
from pymysql import OperationalError
import traceback

from components.emperor import Vassal
from components.common import log_message
from components.cmdrunner import call_subprocess


# pylint: disable=W0612,W0221,W0702


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

    @property
    def id(self):
        return "{}.{}".format(self.owner, self.config_ext)

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

    @property
    def config_ext(self):
        return "mongo"

    @coroutine
    def initialize(self):
        if not os.path.exists(self.__path__):
            log_message("Creating directory for {}".format(self.__owner__), component="Roots")
            os.makedirs(self.__path__)

            proc = subprocess.Popen([
                "mongod",
                "--dbpath={}".format(self.__path__),
                "--port={}".format(self.__port__),
                "--bind_ip=127.0.0.1",
                "--noauth",
                "--logpath={}".format(os.path.join(self.__path__, "log.txt")),
                "--logappend"
            ])

            yield self.wait(auth=False)

            client = motor.MotorClient("127.0.0.1", self.__port__)
            yield client[self.__database__].add_user(
                name=self.__username__,
                password=self.__password__,
                roles=["readWrite"]
            )

            proc.terminate()
            proc.wait()

    @coroutine
    def wait(self, timeout=60, auth=True):
        t = timeout
        client = motor.MotorClient("mongodb://127.0.0.1:{}".format(self.__port__), connectTimeoutMS=500)

        if auth:
            client[self.__database__].authenticate(self.__username__, self.__password__)
        while t >= 0:
            t -= 1
            try:
                yield client[self.__database__].eval("help")
                raise Return(True)
            except motor.pymongo.errors.AutoReconnect:
                pass
            except motor.pymongo.errors.OperationFailure:
                raise Return(True)
            yield Task(IOLoop.current().add_timeout, time.time() + 2)

        raise Return(False)

    def __get_config__(self):
        return """[uwsgi]
master=true
attach-daemon=mongod --dbpath={0} --port={1} --auth --logpath={2} --logappend
""".format(self.__path__, self.__port__, os.path.join(self.__path__, "log.txt"))


class MongoShared(Battery):

    @property
    def config_ext(self):
        return "mongo_shared"

    @coroutine
    def initialize(self):
        client = motor.MotorClient(
            "mongodb://{}:{}@127.0.0.1:{}/admin".format(
                "admin",
                self.__rootpass__,
                self.__port__
            )
        )
        db = client[str(self.__database__)]
        yield db.add_user(self.__username__, self.__password__, roles=["readWrite"])

    @coroutine
    def wait(self):
        pass

    def start(self):
        pass

    def stop(self):
        pass


class MysqlShared(Battery):

    def __init__(self, *args, **kwargs):
        super(MysqlShared, self).__init__(*args, **kwargs)
        self.__username__ = self.__database__[len(self.__database__)-16:]

    @property
    def config_ext(self):
        return "mysql_shared"

    @coroutine
    def initialize(self):
        try:
            db = pymysql.connect(
                host="127.0.0.1",
                port=self.__port__,
                user="root",
                passwd=self.__rootpass__
            )

            cur = db.cursor()
            cur.execute(
                "CREATE DATABASE `{0}` CHARACTER SET utf8 COLLATE utf8_general_ci;".format(
                    self.__database__
                )
            )
            cur.execute(
                "GRANT ALL PRIVILEGES ON {0}.* TO '{1}'@'%' IDENTIFIED BY '{2}' WITH GRANT OPTION;".format(
                    self.__database__,
                    self.__username__,
                    self.__password__
                )
            )
            cur.execute("FLUSH PRIVILEGES;")
            db.close()
        except:
            print(traceback.format_exc())

    @coroutine
    def wait(self):
        pass

    def start(self):
        pass

    def stop(self):
        pass
