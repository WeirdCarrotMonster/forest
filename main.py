#!/usr/bin/env python2
# -*- coding: utf-8 -*- 

from __future__ import print_function
import sys
import os
import tornado.ioloop
import tornado.web
import simplejson as json
from components.trunk import Trunk
from components.roots import Roots
from components.branch import Branch

file = sys.argv[1]  # TODO: проверка на наличие параметра и т.п.
FOREST_DIR = os.path.dirname(os.path.realpath(__file__))
PID_DIR = os.path.join(FOREST_DIR, 'pid')

json_data = open(os.path.join(FOREST_DIR, file))
SETTINGS = json.load(json_data)
json_data.close()

# Определяем слушателей по ролям
listeners = []
settings = {}
if SETTINGS["role"] == "roots":
    print("Setting role: roots")
    listeners.append((r"/", Roots))
    settings = SETTINGS["settings"]

if SETTINGS["role"] == "trunk":
    print("Setting role: trunk")
    listeners.append((r"/", Trunk))
    settings = SETTINGS["settings"]

if SETTINGS["role"] == "branch":
    print("Setting role: branch")
    listeners.append((r"/", Branch))
    settings = SETTINGS["settings"]

# Создаем и запускаем приложение
application = tornado.web.Application(listeners)
if SETTINGS["role"] == "branch":
    application.leaves = []
application.settings = settings
print("Listening on: {0}:{1}".format(SETTINGS["connections"]["address"], SETTINGS["connections"]["port"]))
application.listen(SETTINGS["connections"]["port"], SETTINGS["connections"]["address"])
tornado.ioloop.IOLoop.instance().start()