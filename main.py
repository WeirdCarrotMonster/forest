#!/usr/bin/env python2
# -*- coding: utf-8 -*-

from __future__ import print_function, unicode_literals
import sys
import os
import signal
from tornado.ioloop import IOLoop
from zmq.eventloop import ioloop

import tornado.web
import simplejson as json
from components.api.settings import CommonLeafSettingsHandler
from components.api.species import SpeciesHandler
from components.pages.views import Login, Index

from components.trunk import Trunk
try:
    from components.roots import Roots
    ROOTS_CAPABLE = True
except ImportError:
    ROOTS_CAPABLE = False
from components.branch import Branch
from components.air import Air
from components.common import log_message
from components.api.leaves import LeavesHandler, LeafLogsHandler, LeafHandler, LeafSettingsHandler

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

ioloop.install()
loop = IOLoop.instance()

LISTENERS = [
    (r'/static/(.*)',
     tornado.web.StaticFileHandler,
     {'path': os.path.join(FOREST_DIR, 'static')}),

    (r"/login", Login),

    (r"/api/leaves", LeavesHandler),
    (r"/api/leaves/settings", CommonLeafSettingsHandler),
    (r"/api/leaves/([^/]*)", LeafHandler),
    (r"/api/leaves/([^/]*)/logs", LeafLogsHandler),
    (r"/api/leaves/([^/]*)/settings", LeafSettingsHandler),

    (r"/api/species", SpeciesHandler),
    (r"/(.*)", Index)
]
base_settings = SETTINGS["settings"]
base_settings["REALPATH"] = FOREST_DIR

trunk_settings = SETTINGS["connections"]
base_settings.update(trunk_settings)

APPLICATION = Trunk(base_settings, handlers=LISTENERS)
log_message("Setting role: {0}".format(SETTINGS["roles"].keys()))

if "air" in SETTINGS["roles"].keys():
    role_settings = SETTINGS["roles"]["air"]
    air = Air(role_settings, APPLICATION)
    APPLICATION.air = air
    clbk = tornado.ioloop.PeriodicCallback(air.periodic_event, 5000)
    clbk.start()

if "roots" in SETTINGS["roles"].keys():
    if not ROOTS_CAPABLE:
        raise Exception("Instance is configured to work as Roots, "
                        "but not capable to do so.")
    role_settings = SETTINGS["roles"]["roots"]
    roots = Roots(role_settings, APPLICATION)
    APPLICATION.roots = roots
    clbk = tornado.ioloop.PeriodicCallback(roots.periodic_event, 5000)
    clbk.start()

if "branch" in SETTINGS["roles"].keys():
    role_settings = SETTINGS["roles"]["branch"]
    branch = Branch(role_settings, APPLICATION)
    APPLICATION.branch = branch
    clbk = tornado.ioloop.PeriodicCallback(branch.periodic_event, 5000)
    clbk.start()


APPLICATION.publish_self()
# Запускаем приложение
log_message("Listening on: {0}:{1}".format(
    trunk_settings["trunk_host"],
    trunk_settings["trunk_port"])
)
APPLICATION.listen(
    trunk_settings["trunk_port"],
    trunk_settings["trunk_host"]
)


def cleanup(signum=None, frame=None):
    if signum:
        log_message("Got signum: {0}".format(signum), end="\r")

    log_message("Cleaning up...")
    APPLICATION.cleanup()
    log_message("Done!")
    sys.exit(0)

for sig in [signal.SIGTERM, signal.SIGINT, signal.SIGQUIT]:
    signal.signal(sig, cleanup)

loop.start()
