# -*- coding: utf-8 -*-

from __future__ import unicode_literals, print_function

import random
import string

from tornado.gen import coroutine
import pymysql
import motor
import traceback


# pylint: disable=W0612,W0221,W0702


class Battery(object):

    def __init__(
            self,
            path=None,
            port=None,
            owner=None,
            rootpass=None,
            username=None,
            password=None,
            database=None,
            ):
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


class Mongo(Battery):

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


class MySQL(Battery):

    def __init__(self, *args, **kwargs):
        super(MySQL, self).__init__(*args, **kwargs)
        self.__username__ = self.__database__[len(self.__database__)-16:]

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
                "GRANT ALL PRIVILEGES ON `{0}`.* TO '{1}'@'%' IDENTIFIED BY '{2}' WITH GRANT OPTION;".format(
                    self.__database__,
                    self.__username__,
                    self.__password__
                )
            )
            cur.execute("FLUSH PRIVILEGES;")
            db.close()
        except:
            print(traceback.format_exc())
