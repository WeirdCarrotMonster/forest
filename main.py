#!/usr/bin/env python2
# -*- coding: utf-8 -*- 

import os
import tornado.ioloop
import tornado.web
import simplejson as json

FOREST_DIR = os.path.dirname(os.path.realpath(__file__))
PID_DIR = os.path.join(FOREST_DIR, 'pid')

json_data = open(os.path.join(FOREST_DIR, "settings.json"))
SETTINGS = json.load(json_data)
json_data.close()


class MainHandler(tornado.web.RequestHandler):
	def get(self):
		self.write("Hello, world")

	def post(self):
		self.write("Hello, world")

application = tornado.web.Application([
    (r"/", MainHandler),
])

if __name__ == "__main__":
	application.listen(8888)
	tornado.ioloop.IOLoop.instance().start()