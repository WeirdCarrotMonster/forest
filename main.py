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
from components.branch import Branch
from components.air import Air, get_leaves_proxy
from components.common import CommonListener, TransparentListener, WebSocketListener, log_message

if len(sys.argv) < 2:
    log_message(
        """
        Launch error: unknown number of arguments
        Specify settings filename /and shell_config
        To get working lighttpd include_shell config
        """
    )
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
settings = SETTINGS["settings"]

if not SETTINGS["role"] in ["roots", "trunk", "branch", "air"]:
    log_message("Configuration error: unknown role '{0}'".format(SETTINGS["role"]))
    sys.exit(0)

application = None
log_message("Setting role: {0}".format(SETTINGS["role"]))

if SETTINGS["role"] == "roots":
    listeners.append((r"/", CommonListener))
    application = Roots(settings, handlers=listeners)

if SETTINGS["role"] == "trunk":
    listeners.append((r"/", TransparentListener))
    listeners.append((r"/websocket", WebSocketListener))
    application = Trunk(settings, handlers=listeners)

if SETTINGS["role"] == "branch":
    listeners.append((r"/", CommonListener))
    application = Branch(settings, handlers=listeners)

if SETTINGS["role"] == "air":
    listeners.append((r"/", CommonListener))
    application = Air(settings, handlers=listeners)

# Создаем и запускаем приложение
log_message("Listening on: {0}:{1}".format(
    SETTINGS["connections"]["address"], 
    SETTINGS["connections"]["port"])
)
application.listen(SETTINGS["connections"]["port"], SETTINGS["connections"]["address"])


def cleanup(signum=None, frame=None):
    if signum:
        log_message("Got signum: {0}".format(signum))
    try:
        log_message("Cleaning up...")
        application.shutdown_leaves()
    except:
        pass
    finally:
        log_message("Done!")
    sys.exit(0)

for sig in [signal.SIGTERM, signal.SIGINT, signal.SIGHUP, signal.SIGQUIT]:
    signal.signal(sig, cleanup)

tornado.ioloop.IOLoop.instance().start()