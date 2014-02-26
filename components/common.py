# -*- coding: utf-8 -*-

from __future__ import print_function
import tornado.web
import tornado.websocket
import simplejson as json
from components.shadow import encode, decode
from datetime import datetime
from bson import json_util
import traceback
import os
from multiprocessing import Process
from pymongo import MongoReplicaSetClient


def get_connection(host, port, user, password):
    con = MongoReplicaSetClient(host, port, replicaSet="forest")
    con.admin.authenticate(user, password)
    return con


def run_parallel(fns):
    proc = []
    for fn in fns:
        p = Process(target=fn)
        p.start()
        proc.append(p)
    for p in proc:
        p.join()


class ArgumentMissing(Exception):
    pass


class LogicError(Exception):
    pass


class Warning(Exception):
    pass


def check_arguments(message, required_args, optional_args=None):
    data = {}
    for arg in required_args:
        value = message.get(arg, None)
        if not value:
            raise ArgumentMissing(arg)
        else:
            data[arg] = value
    for arg in optional_args or []:
        data[arg[0]] = message.get(arg[0], arg[1])
    return data


class WebSocketListener(tornado.websocket.WebSocketHandler):
    def open(self):
        log_message("Socket opened")

    def get_current_user(self):
        return self.get_secure_cookie("user")

    def on_message(self, socket_message):
        try:
            message = json.loads(
                socket_message
            )
        except ValueError:
            self.write_message(json.dumps(
                {
                    "result": "failure",
                    "message": "Failed to decode message",
                    "details": traceback.format_exc()
                }, default=json_util.default))
            return

        try:
            response = self.application.process_message(
                message,
                socket=self,
                user=self.get_current_user()
            )
        except Exception:
            response = {
                "result": "failure",
                "message": "Internal server error",
                "details": traceback.format_exc()
            }
        self.write_message(json.dumps(response, default=json_util.default))

    def send_message(self, message):
        try:
            self.write_message(json.dumps(message))
        except:
            pass

    def on_close(self):
        log_message("Socket closed")


class CommonListener(tornado.web.RequestHandler):
    def get(self):
        self.write("")

    def post(self):
        try:
            message = json.loads(
                decode(self.request.body,
                       self.application.settings["secret"])
            )
        except ValueError:
            self.write(json.dumps(
                {
                    "result": "failure",
                    "message": "Failed to decode message",
                    "details": traceback.format_exc()
                }, default=json_util.default))
            return

        try:
            response = self.application.process_message(message)
        except ValueError:
            response = {
                "result": "failure",
                "message": "Internal server error",
                "details": traceback.format_exc()
            }
        except ArgumentMissing, arg:
            return {
                "result": "failure",
                "message": "Missing argument: {0}".format(arg.message)
            }
        self.write(encode(
            json.dumps(response, default=json_util.default),
            self.application.settings["secret"])
        )


class TransparentListener(tornado.web.RequestHandler):
    def get_current_user(self):
        return self.get_secure_cookie("user")

    @tornado.web.asynchronous
    def get(self, page):
        # Вот тут выдаются страницы
        # Все те, что не статика
        # Потому что мне так велел велоцираптор иисус
        try:
            response = self.application.process_page(
                page,
                self.get_current_user()
            )
            with open(os.path.join(self.application.settings["REALPATH"],
                      response), 'r') as page_file:
                self.finish(page_file.read())
        except Exception as e:
            self.finish(e.message)

    @tornado.web.asynchronous
    def post(self, stuff):
        # Вот тут обрабатывается API
        # Строго через POST
        # Потому что мне так велел летающий макаронный монстр с фрикадельками
        try:
            message = json.loads(self.request.body)
        except ValueError:
            self.finish(json.dumps(
                {
                    "result": "failure",
                    "message": "Failed to decode message",
                    "details": traceback.format_exc()
                }, default=json_util.default))
            return

        try:
            response = self.application.process_message(
                message,
                handler=self,
                user=self.get_current_user()
            )
        except ArgumentMissing, arg:
            response = {
                "result": "failure",
                "message": "Missing argument: {0}".format(arg.message)
            }
        except LogicError, arg:
            response = {
                "result": "failure",
                "message": "{0}".format(arg.message)
            }
        except Warning, arg:
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
        self.finish(json.dumps(response, default=json_util.default))


def log_message(message, component="Forest"):
    print("[{0}][{1}]{2}".format(datetime.now(), component, message))
