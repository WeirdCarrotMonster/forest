# -*- coding: utf-8 -*-

from __future__ import print_function, unicode_literals

import hashlib
import os
import traceback
from datetime import datetime
from multiprocessing import Process
from threading import Lock, Thread

import bson
import simplejson as json
import tornado.gen
import tornado.web
from simplejson import JSONEncoder
from tornado import gen
from functools import wraps


class LogicError(Exception):
    pass


class CustomEncoder(JSONEncoder):
    def default(self, obj):
        if type(obj) == datetime:
            return obj.isoformat()
        elif type(obj) == bson.objectid.ObjectId:
            return str(obj)
        else:
            return JSONEncoder.default(self, obj)


class TransparentListener(tornado.web.RequestHandler):
    def get_current_user(self):
        return self.get_secure_cookie("user")

    def get(self, page):
        # Вот тут выдаются страницы
        # Все те, что не статика
        # Потому что мне так велел велоцираптор иисус
        log_message("Page request: {0}".format(page))
        try:
            response = self.application.process_page(
                page,
                self.get_current_user()
            )
            with open(os.path.join(self.application.settings["REALPATH"],
                      response), 'r') as page_file:
                self.write(page_file.read())
            self.finish()
        except Exception as e:
            if e.message == 401:
                self.redirect('/login', permanent=True)
            elif e.message == 404:
                self.redirect('/', permanent=True)

    @tornado.web.asynchronous
    @gen.engine
    def post(self, stuff):
        # Вот тут обрабатывается API
        # Строго через POST
        # Потому что мне так велел летающий макаронный монстр с фрикадельками
        try:
            message = json.loads(self.request.body)
            log_message("API request: {}".format(message.get("function", None)))
        except ValueError:
            self.finish(json.dumps(
                {
                    "result": "failure",
                    "message": "Failed to decode message",
                    "details": traceback.format_exc()
                }, cls=CustomEncoder))
            return

        try:
            # TODO: валидацию понадежнее
            message_secret = message.get("secret")
            response = yield gen.Task(self.application.process_message, **{
                "message": message,
                "user": self.get_current_user(),
                "inner": self.application.settings["secret"] == message_secret,
                "handler": self
            })
        except TypeError as arg:
            response = {
                "result": "failure",
                "message": "Missing argument: {}".format(arg.message)
            }
        except LogicError as arg:
            response = {
                "result": "failure",
                "message": "{0}".format(arg.message)
            }
        except Warning as arg:
            response = {
                "result": "warning",
                "message": "{0}".format(arg.message)
            }
        except Exception:
            response = {
                "result": "failure",
                "message": "Internal server error",
                "details": traceback.format_exc()
            }
        self.set_header("Content-Type", "application/json")
        self.finish(json.dumps(response, cls=CustomEncoder))


def log_message(message, component="Forest", end="\n"):
    print("[{0}][{1}]{2}".format(datetime.now(), component, message), end=end)
