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
from components.roots import Roots
from components.branch import Branch
from components.air import Air
from components.common import TransparentListener, log_message

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
trunk_settings = SETTINGS["connections"]
trunk_settings.update(base_settings)
trunk_settings["REALPATH"] = FOREST_DIR
APPLICATION = Trunk(trunk_settings, handlers=LISTENERS)
log_message("Setting role: {0}".format(SETTINGS["roles"].keys()))

# TODO: Переписать этот цикл при возможности. Страшно смотреть
for role, role_settings in SETTINGS["roles"].items():
    if not role in ["roots", "branch", "air"]:
        log_message("Unknown role: {0}".format(role))
        sys.exit(1)
    role_settings.update(base_settings)
    if role == "branch":
        branch = Branch(role_settings)
        APPLICATION.branch = branch
        APPLICATION.functions["branch.update_state"] = branch.update_state
        APPLICATION.functions["branch.update_repository"] = branch.update_repo
        APPLICATION.functions["branch.known_leaves"] = branch.known_leaves
        APPLICATION.functions["branch.get_leaf_logs"] = branch.get_leaf_logs
    elif role == "air":
        air = Air(role_settings)
        APPLICATION.air = air
        APPLICATION.functions["air.update_state"] = air.update_state
    elif role == "roots":
        roots = Roots(role_settings)
        APPLICATION.roots = roots
        APPLICATION.functions["roots.update_state"] = roots.update_state

APPLICATION.publish_self()
# Запускаем приложение
log_message("Listening on: {0}:{1}".format(
    SETTINGS["connections"]["host"],
    SETTINGS["connections"]["port"])
)
APPLICATION.listen(
    SETTINGS["connections"]["port"],
    SETTINGS["connections"]["host"]
)


def cleanup(signum=None, frame=None):
    if signum:
        log_message("Got signum: {0}".format(signum))

    log_message("Cleaning up...")
    APPLICATION.cleanup()
    log_message("Done!")
    sys.exit(0)

for sig in [signal.SIGTERM, signal.SIGINT, signal.SIGHUP, signal.SIGQUIT]:
    signal.signal(sig, cleanup)

loop.start()
