# -*- coding: utf-8 -*-

from __future__ import print_function
import tornado.web
import simplejson as json
from components.shadow import encode, decode


class CommonListener(tornado.web.RequestHandler):
    def get(self):
        self.write("")

    def post(self):
        try:
            message = json.loads(decode(self.request.body, self.application.settings["secret"]))
        except Exception, e:
            self.write(json.dumps({
                "result": "failure",
                "message": "Failed to decode message",
                "details": e.message
            }))
            return

        try:
            response = self.application.process_message(message)
        except Exception, e:
            response = json.dumps({
                "result": "failure",
                "message": "Internal server error",
                "details": e.message
            })
        self.write(encode(response, self.application.settings["secret"]))


class TransparentListener(tornado.web.RequestHandler):
    def get(self):
        self.write("")

    def post(self):
        try:
            print("Got request:\n{0}".format(self.request.body))
            message = json.loads(self.request.body)
        except Exception, e:
            self.write(json.dumps({
                "result": "failure",
                "message": "Failed to decode message",
                "details": e.message
            }))
            return

        response = self.application.process_message(message)
        self.write(response)