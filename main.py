#!/usr/bin/env python2
# -*- coding: utf-8 -*- 

from __future__ import print_function
import sys
import os
import signal
import tornado.ioloop
import tornado.web
import simplejson as json
from components.trunk import Trunk
from components.roots import Roots
from components.branch import Branch, init_leaves
from components.air import Air, get_leaves_proxy

if len(sys.argv) < 2:
    print("Launch error: unknown number of arguments")
    print("Specify settings filename /and shell_config")
    print("To get working lighttpd include_shell config")
    sys.exit(0)

file = sys.argv[1]
FOREST_DIR = os.path.dirname(os.path.realpath(__file__))
PID_DIR = os.path.join(FOREST_DIR, 'pid')

json_data = open(os.path.join(FOREST_DIR, file))
SETTINGS = json.load(json_data)
json_data.close()

if len(sys.argv) == 3 and sys.argv[2] == "shell_config":
    get_leaves_proxy(SETTINGS)
    sys.exit(0)

# Определяем слушателей по ролям
listeners = []

if not SETTINGS["role"] in ["roots", "trunk", "branch", "air"]:
    print("Configuration error: unknown role")
    sys.exit(0)

if SETTINGS["role"] == "roots":
    print("Setting role: roots")
    listeners.append((r"/", Roots))

if SETTINGS["role"] == "trunk":
    print("Setting role: trunk")
    listeners.append((r"/", Trunk))

if SETTINGS["role"] == "branch":
    print("Setting role: branch")
    listeners.append((r"/", Branch))

if SETTINGS["role"] == "air":
    print("Setting role: air")
    listeners.append((r"/", Air))

settings = SETTINGS["settings"]

# Создаем и запускаем приложение
application = tornado.web.Application(listeners)
application.settings = settings

if SETTINGS["role"] == "branch":
    application.leaves = []
    application.settings["port_range"] = range(application.settings["port_range_begin"], application.settings["port_range_end"])
    init_leaves(application)

print("Listening on: {0}:{1}".format(SETTINGS["connections"]["address"], SETTINGS["connections"]["port"]))
application.listen(SETTINGS["connections"]["port"], SETTINGS["connections"]["address"])


def cleanup(signum=None, frame=None):
    if signum:
        print("Got signum: {0}".format(signum))
    print("Cleaning up...")
    try:
        for leaf in application.leaves:
            leaf.stop()
    except:
        pass
    print("Done!")
    sys.exit(0)

for sig in [signal.SIGTERM, signal.SIGINT, signal.SIGHUP, signal.SIGQUIT]:
    signal.signal(sig, cleanup)

tornado.ioloop.IOLoop.instance().start()