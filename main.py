#!/usr/bin/env python2
# -*- coding: utf-8 -*-

from __future__ import print_function, unicode_literals
import sys
import os
import signal

from tornado.ioloop import IOLoop
from zmq.eventloop import ioloop
import simplejson as json

from components.trunk import Trunk
from components.common import log_message

if len(sys.argv) < 2:
    log_message(
        """
        Launch error: unknown number of arguments
        Specify settings filename
        """
    )
    sys.exit(0)

filename = sys.argv[1]

with open(filename) as config:
    settings = json.load(config)

ioloop.install()
loop = IOLoop.instance()

listeners = []

if "air" in settings.keys():
    from components.air import air_handlers
    listeners += air_handlers

application = Trunk(settings["base"], handlers=listeners)

if "air" in settings.keys():
    from components.air import Air
    application.air = Air(
        application,
        settings["air"]["host"],
        settings["air"]["port"]
    )

application.listen(
    settings["base"]["port"],
    settings["base"]["host"]
)


def cleanup(signum=None, frame=None):
    if signum != signal.SIGQUIT:
        log_message("Cleaning up...", begin="\r")
        application.cleanup()
        log_message("Done!")
    else:
        log_message("Shutting down forest, keeping uwsgi")

    sys.exit(0)

for sig in [signal.SIGTERM, signal.SIGINT, signal.SIGQUIT]:
    signal.signal(sig, cleanup)

loop.start()
