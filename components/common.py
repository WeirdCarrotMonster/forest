# -*- coding: utf-8 -*-

from __future__ import print_function
import tornado.web
import tornado.websocket
import simplejson as json
from shadow import encode, decode
from datetime import datetime
from bson import BSON
from bson import json_util


class WebSocketListener(tornado.websocket.WebSocketHandler):
    def open(self):
        log_message("Socket opened")

    def on_message(self, socket_message):
        try:
            message = json.loads(
                socket_message
            )
        except Exception, e:
            self.write_message(json.dumps({
                "result": "failure",
                "message": "Failed to decode message",
                "details": e.message
            }, default=json_util.default))
            return

        try:
            response = self.application.process_message(message, socket=self)
        except Exception, e:
            response = {
                "result": "failure",
                "message": "Internal server error",
                "details": str(e)
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
        except Exception, e:
            self.write(json.dumps({
                "result": "failure",
                "message": "Failed to decode message",
                "details": e.message
            }, default=json_util.default))
            return

        try:
            response = self.application.process_message(message)
        except Exception, e:
            response = {
                "result": "failure",
                "message": "Internal server error",
                "details": str(e)
            }
        self.write(encode(json.dumps(response, default=json_util.default), self.application.settings["secret"]))


class TransparentListener(tornado.web.RequestHandler):
    def get(self):
        self.write("")

    def post(self):
        try:
            message = json.loads(self.request.body)
        except Exception, e:
            self.write(json.dumps({
                "result": "failure",
                "message": "Failed to decode message",
                "details": e.message
            }, default=json_util.default))
            return

        response = self.application.process_message(message)
        self.write(json.dumps(response, default=json_util.default))


def log_message(message, component="Forest"):
    print("[{0}][{1}]{2}".format(datetime.now(), component, message))