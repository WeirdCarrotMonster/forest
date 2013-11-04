# -*- coding: utf-8 -*-

from __future__ import print_function
import tornado.web
import simplejson as json
from components.shadow import encode, decode


class CommonListener(tornado.web.RequestHandler):
    def get(self):
        self.write("Hello to you from branch!")

    def post(self):
        try:
            message = json.loads(decode(self.get_argument('message', None), self.application.settings["secret"]))
        except:
            self.write(json.dumps({
                "result": "failure",
                "message": "failed to decode message"
            }))
            return
        # Далее message - тело запроса

        response = self.application.process_message(message)
        self.write(encode(response, self.application.settings["secret"]))
