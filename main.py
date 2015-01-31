#!/usr/bin/env python2
# -*- coding: utf-8 -*-

from __future__ import print_function, unicode_literals

import os
import sys
import shutil
import signal
import argparse

from tornado.ioloop import IOLoop
from zmq.eventloop import ioloop
import simplejson as json

from components.trunk import Trunk
from components.common import log_message


parser = argparse.ArgumentParser(description='Run your own Forest')
subparsers = parser.add_subparsers(dest="command")

parser_run = subparsers.add_parser(
    'run', help="Forest launch mode"
)

parser_run.add_argument(
    '--config', '-c', type=argparse.FileType('r'),
    default=os.path.join(os.path.expanduser("~"), ".forest.json"), help="use specified Forest configuration file"
)

parser_check = subparsers.add_parser(
    'check', help="check Forest configuration and exit"
)

parser_check.add_argument(
    '--config', '-c', type=argparse.FileType('r'),
    default=os.path.join(os.path.expanduser("~"), ".forest.json"), help="use specified Forest configuration file"
)

parser_prepare = subparsers.add_parser(
    'prepare', help="prepare directories and binaries as specified in configuration file"
)

parser_prepare.add_argument(
    '--config', '-c', type=argparse.FileType('r'),
    default=os.path.join(os.path.expanduser("~"), ".forest.json"), help="use specified Forest configuration file"
)

parser_prepare.add_argument(
    '--force', '-f',
    dest='force', action='store_true', help="force rewrite uwsgi binary and plugins"
)

parser_shell = subparsers.add_parser(
    'shell', help="run Forest shell"
)

parser_shell.add_argument(
    '--config', '-c', type=argparse.FileType('r'),
    default=os.path.join(os.path.expanduser("~"), ".forest_shell.json"), help="use specified Forest connection file"
)

args = parser.parse_args()
settings = json.load(args.config)

if args.command == "prepare":
    from utils.build import build_uwsgi

    emperor_dir = settings["base"].get("emperor", os.path.join(settings["base"]["root"], "emperor"))

    if os.path.exists(emperor_dir) and args.force:
        print("Cleaning existing executables")
        shutil.rmtree(os.path.join(emperor_dir, "bin"))

    if not os.path.exists(os.path.join(emperor_dir, "bin")):
        print("Creating emperor directory at {}".format(emperor_dir))

        os.makedirs(os.path.join(emperor_dir, "bin"))
        if not os.path.exists(os.path.join(emperor_dir, "vassals")):
            os.makedirs(os.path.join(emperor_dir, "vassals"))

        print("Building uwsgi")
        build_uwsgi(os.path.join(emperor_dir, "bin"))

    sys.exit(0)
elif args.command == "check":
    sys.exit(0)
elif args.command == "shell":
    from utils.shell import ShellTool
    ShellTool(**settings).cmdloop()
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
        log_message("Shutting down forest, keeping uwsgi", begin="\r")

    sys.exit(0)

for sig in [signal.SIGTERM, signal.SIGINT, signal.SIGQUIT]:
    signal.signal(sig, cleanup)

loop.start()
