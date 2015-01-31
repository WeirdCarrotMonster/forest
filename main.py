#!/usr/bin/env python2
# -*- coding: utf-8 -*-

from __future__ import print_function, unicode_literals

import os
import sys
import shutil
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
    sys.exit(1)

filename = sys.argv[1]

with open(filename) as config:
    settings = json.load(config)

if len(sys.argv) == 3 and sys.argv[2] == "prepare":
    from build import build_uwsgi

    emperor_dir = settings["base"].get("emperor", os.path.join(settings["base"]["root"], "emperor"))
    if not os.path.exists(emperor_dir):
        print("Creating emperor directory at {}".format(emperor_dir))
        os.makedirs(emperor_dir)
        os.makedirs(os.path.join(emperor_dir, "bin"))
        os.makedirs(os.path.join(emperor_dir, "vassals"))
    else:
        print("Cleaning existing executables")
        shutil.rmtree(os.path.join(emperor_dir, "bin"))
        os.makedirs(os.path.join(emperor_dir, "bin"))

    print("Building uwsgi")
    build_uwsgi(os.path.join(emperor_dir, "bin"))
    sys.exit(0)

ioloop.install()
loop = IOLoop.instance()

listeners = []

if "air" in settings.keys():
    from components.air import air_handlers
    listeners += air_handlers

if "roots" in settings.keys():
    from components.roots import roots_handlers
    listeners += roots_handlers

if "branch" in settings.keys():
    from components.branch import branch_handlers
    listeners += branch_handlers

if "druid" in settings.keys():
    from components.druid import druid_handlers
    listeners += druid_handlers

application = Trunk(settings["base"], handlers=listeners)

if "air" in settings.keys():
    from components.air import Air
    application.air = Air(
        application,
        settings["air"]["host"],
        settings["air"]["port"]
    )

if "roots" in settings.keys():
    from components.roots import Roots
    application.roots = Roots(
        application,
        settings["roots"]
    )

if "branch" in settings.keys():
    from components.branch import Branch
    application.branch = Branch(
        application,
        settings["branch"]
    )

if "druid" in settings.keys():
    from components.druid import Druid
    application.druid = Druid(
        application,
        settings["druid"]
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
