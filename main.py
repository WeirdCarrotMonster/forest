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
from components.air import Air
from components.common import CommonListener, TransparentListener, \
    WebSocketListener, log_message

if len(sys.argv) < 2:
    log_message(
        """
        Launch error: unknown number of arguments
        Specify settings filename
        """
    )
    sys.exit(0)

FILENAME = sys.argv[1]
FOREST_DIR = os.path.dirname(os.path.realpath(__file__))

JSON_DATA = open(os.path.join(FOREST_DIR, FILENAME))
SETTINGS = json.load(JSON_DATA)
SETTINGS["settings"]["REALPATH"] = FOREST_DIR
JSON_DATA.close()

# Определяем слушателей по ролям
LISTENERS = []
loop = tornado.ioloop.IOLoop.instance()

if not SETTINGS["role"] in ["roots", "trunk", "branch", "air"]:
    log_message(
        "Configuration error: unknown role '{0}'".format(SETTINGS["role"])
    )
    sys.exit(0)

APPLICATION = None
log_message("Setting role: {0}".format(SETTINGS["role"]))

if SETTINGS["role"] == "roots":
    LISTENERS.append((r"/", CommonListener))
    APPLICATION = Roots(SETTINGS["settings"], handlers=LISTENERS)

if SETTINGS["role"] == "trunk":
    LISTENERS.append((r'/static/(.*)', tornado.web.StaticFileHandler,
                      {'path': os.path.join(FOREST_DIR, 'static')}))
    LISTENERS.append((r"/(.*)", TransparentListener))
    APPLICATION = Trunk(SETTINGS["settings"], handlers=LISTENERS)

    period_cbk = tornado.ioloop.PeriodicCallback(
        APPLICATION.log_stats, 1000 * 60 * 10, loop)
    period_cbk.start()

if SETTINGS["role"] == "branch":
    LISTENERS.append((r"/", CommonListener))
    APPLICATION = Branch(SETTINGS["settings"], handlers=LISTENERS)

if SETTINGS["role"] == "air":
    LISTENERS.append((r"/", CommonListener))
    APPLICATION = Air(SETTINGS["settings"], handlers=LISTENERS)

# Создаем и запускаем приложение
log_message("Listening on: {0}:{1}".format(
    SETTINGS["connections"]["address"],
    SETTINGS["connections"]["port"])
)
APPLICATION.listen(
    SETTINGS["connections"]["port"],
    SETTINGS["connections"]["address"]
)


def cleanup(signum=None, frame=None):
    if signum:
        log_message("Got signum: {0}, frame {1}".format(signum, frame))
    try:
        log_message("Cleaning up...")
        APPLICATION.cleanup()
    except AttributeError:
        pass
    finally:
        log_message("Done!")
    sys.exit(0)

for sig in [signal.SIGTERM, signal.SIGINT, signal.SIGHUP, signal.SIGQUIT]:
    signal.signal(sig, cleanup)

loop.start()
