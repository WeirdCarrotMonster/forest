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


class ArgumentMissing(Exception):
    pass


def check_arguments(message, required_args):
    data = {}
    for arg in required_args:
        value = message.get(arg, None)
        if not value:
            raise ArgumentMissing(arg)
        else:
            data[arg] = value
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
            self.write_message(json.dumps({
                "result": "failure",
                "message": "Failed to decode message",
                "details": traceback.format_exc()
            }, default=json_util.default))
            return

        try:
            response = self.application.process_message(message, socket=self, user=self.get_current_user())
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
            self.write(json.dumps({
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
        self.write(encode(
            json.dumps(response, default=json_util.default), 
            self.application.settings["secret"])
        )


class TransparentListener(tornado.web.RequestHandler):
    def get_current_user(self):
        return self.get_secure_cookie("user")

    def get(self, page):
        # Вот тут выдаются страницы
        # Все те, что не статика
        # Потому что мне так велел велоцираптор иисус
        try:
            response = self.application.process_page(page, self.get_current_user())
            with open(os.path.join(self.application.settings["REALPATH"], response), 'r') as file:
                self.write(file.read())
        except Exception as e:
            self.write(e.message)

    def post(self, stuff):
        # Вот тут обрабатывается API
        # Строго через POST
        # Потому что мне так велел летающий макаронный монстр с фрикадельками
        try:
            message = json.loads(self.request.body)
        except ValueError:
            self.write(json.dumps({
                "result": "failure",
                "message": "Failed to decode message",
                "details": traceback.format_exc()
            }, default=json_util.default))
            return

        response = self.application.process_message(message, handler=self, user=self.get_current_user())
        self.set_header("Content-Type", "application/json")
        self.write(json.dumps(response, default=json_util.default))


def log_message(message, component="Forest"):
    print("[{0}][{1}]{2}".format(datetime.now(), component, message))
