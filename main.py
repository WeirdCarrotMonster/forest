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
from components.owl import Owl
from components.common import CommonListener, TransparentListener, \
    WebSocketListener, log_message

if len(sys.argv) < 2:
    log_message(
        """
        Launch error: unknown number of arguments
        Specify settings filename /and shell_config
        To get working lighttpd include_shell config
        """
    )
    sys.exit(0)

FILENAME = sys.argv[1]
FOREST_DIR = os.path.dirname(os.path.realpath(__file__))
PID_DIR = os.path.join(FOREST_DIR, 'pid')

JSON_DATA = open(os.path.join(FOREST_DIR, FILENAME))
SETTINGS = json.load(JSON_DATA)
SETTINGS["settings"]["REALPATH"] = FOREST_DIR
JSON_DATA.close()

if len(sys.argv) == 3 and sys.argv[2] == "shell_config":
    get_leaves_proxy(SETTINGS)
    sys.exit(0)

# Определяем слушателей по ролям
LISTENERS = []
loop = tornado.ioloop.IOLoop.instance()

if not SETTINGS["role"] in ["roots", "trunk", "branch", "air", "owl"]:
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
                      {'path': os.path.join(FOREST_DIR, 'druid/static')}))
    LISTENERS.append((r'/static_new/(.*)', tornado.web.StaticFileHandler,
                      {'path': os.path.join(FOREST_DIR, 'static')}))
    LISTENERS.append((r'/druid/(.*)', tornado.web.StaticFileHandler,
                      {'path': os.path.join(FOREST_DIR, 'druid/html')}))
    LISTENERS.append((r"/websocket", WebSocketListener))
    LISTENERS.append((r"/(.*)", TransparentListener))
    APPLICATION = Trunk(SETTINGS["settings"], handlers=LISTENERS)

    # Частота обновления логов - одна минута
    # TODO: брать из настроек
    PERIOD = 10
    period_cbk = tornado.ioloop.PeriodicCallback(
        APPLICATION.log_stats, 1000 * 60 * PERIOD, loop)
    period_cbk.start()


if SETTINGS["role"] == "branch":
    LISTENERS.append((r"/", CommonListener))
    APPLICATION = Branch(SETTINGS["settings"], handlers=LISTENERS)

if SETTINGS["role"] == "air":
    LISTENERS.append((r"/", CommonListener))
    APPLICATION = Air(SETTINGS["settings"], handlers=LISTENERS)

if SETTINGS["role"] == "owl":
    LISTENERS.append((r"/", CommonListener))
    APPLICATION = Owl(SETTINGS["settings"], handlers=LISTENERS)

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
        APPLICATION.shutdown_leaves()
    except AttributeError:
        pass
    finally:
        log_message("Done!")
    sys.exit(0)

for sig in [signal.SIGTERM, signal.SIGINT, signal.SIGHUP, signal.SIGQUIT]:
    signal.signal(sig, cleanup)

loop.start()
