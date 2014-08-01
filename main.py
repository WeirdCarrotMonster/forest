#!/usr/bin/env python2
# -*- coding: utf-8 -*-

from __future__ import print_function, unicode_literals
import sys
import os
import signal
import tornado.ioloop
import tornado.web
import simplejson as json

from components.trunk import Trunk
try:
    from components.roots import Roots
    ROOTS_CAPABLE = True
except ImportError:
    ROOTS_CAPABLE = False
from components.branch import Branch
from components.air import Air
from components.common import TransparentListener, log_message
import components.druid

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
JSON_DATA.close()

# Определяем слушателей по ролям
loop = tornado.ioloop.IOLoop.instance()

LISTENERS = [
    # Слушаем статику на случай, если не выдаем её чем-нибудь другим
    (r'/static/(.*)',
     tornado.web.StaticFileHandler,
     {'path': os.path.join(FOREST_DIR, 'static')}),
    (r"/(.*)", TransparentListener)
]
base_settings = SETTINGS["settings"]
base_settings["REALPATH"] = FOREST_DIR

trunk_settings = SETTINGS["connections"]

APPLICATION = Trunk(base_settings, handlers=LISTENERS)
log_message("Setting role: {0}".format(SETTINGS["roles"].keys()))

if "air" in SETTINGS["roles"].keys():
    role_settings = SETTINGS["roles"]["air"]
    air = Air(role_settings, APPLICATION)
    APPLICATION.air = air
    APPLICATION.functions.update(air.functions)

if "roots" in SETTINGS["roles"].keys():
    if not ROOTS_CAPABLE:
        raise Exception("Instance is configured to work as Roots, "
                        "but not capable to do so.")
    role_settings = SETTINGS["roles"]["roots"]
    roots = Roots(role_settings, APPLICATION)
    APPLICATION.roots = roots
    APPLICATION.functions.update(roots.functions)

if "branch" in SETTINGS["roles"].keys():
    role_settings = SETTINGS["roles"]["branch"]
    branch = Branch(role_settings, APPLICATION)
    APPLICATION.branch = branch
    APPLICATION.functions.update(branch.functions)

if True:  # Предполагаем, что каждый компонент может выступать в роли интерфейса
    role_settings = {}  # Будут настройки?
    role_settings.update(base_settings)
    druid = components.druid.Druid(role_settings, APPLICATION)
    APPLICATION.druid = druid
    APPLICATION.functions.update(druid.functions)


APPLICATION.publish_self()
# Запускаем приложение
log_message("Listening on: {0}:{1}".format(
    trunk_settings["host"],
    trunk_settings["port"])
)
APPLICATION.listen(
    trunk_settings["port"],
    trunk_settings["host"]
)


def cleanup(signum=None, frame=None):
    if signum:
        log_message("Got signum: {0}".format(signum))

    log_message("Cleaning up...")
    APPLICATION.cleanup()
    log_message("Done!")
    sys.exit(0)


def reload_druid(signum=None, frame=None):
    log_message("Got SIGHUP, reloading web interface module")
    reload(components.druid)
    role_settings = {}  # Будут настройки?
    role_settings.update(base_settings)
    druid = components.druid.Druid(role_settings, APPLICATION)
    APPLICATION.druid = druid
    APPLICATION.functions.update(druid.functions)

for sig in [signal.SIGTERM, signal.SIGINT, signal.SIGQUIT]:
    signal.signal(sig, cleanup)

signal.signal(signal.SIGHUP, reload_druid)

loop.start()
