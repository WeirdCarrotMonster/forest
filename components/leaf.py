# -*- coding: utf-8 -*-
import datetime
import os
import subprocess

import simplejson as json


def enqueue_output(out, queue):
    for line in iter(out.readline, b''):
        queue.put(line)
    out.close()


class Leaf(object):
    def __init__(self,
                 name=None,
                 host="127.0.0.1",
                 path=None,
                 settings=None,
                 fastrouters=None,
                 keyfile=None,
                 address="",
                 leaf_type=None,
                 logger=None,
                 component=None,
                 batteries=None,
                 workers=4,
                 threads=False
                 ):
        self.name = name
        self.host = host
        self.chdir = path
        self.settings = settings or {}
        self.process = None
        self.fastrouters = fastrouters or []
        self.keyfile = keyfile
        self.address = address
        self.type = leaf_type
        self.logger = logger
        self.component = component
        self.batteries = batteries
        self.workers = workers
        self.threads = threads

        self._thread = None
        self._queue = None
        self.logs = []

        self._last_req_measurement = datetime.datetime.now()
        self._last_req_count = 0

    def __ne__(self, other):
        r1 = self.address == other.address
        r2 = self.settings == other.settings
        r3 = self.workers == other.workers
        r4 = self.batteries == other.batteries
        return not all([r1, r2, r3, r4])

    def set_settings(self, settings):
        self.settings = settings

    def get_config(self):
        logs_format = {
            "uri": "%(uri)",
            "method": "%(method)",
            "addr": "%(addr)",
            "host": "%(host)",
            "proto": "%(proto)",
            "status": "%(status)",
            "msecs": "%(msecs)",
            "time": "%(ltime)",
            "size": "%(size)",
            "wid": "%(name)",
        }

        leaf_settings = {
            "static_url": "/static/{0}/".format(self.type["name"])
        }

        config = """
        [uwsgi]
        chdir={chdir}
        heartbeat=10
        module=wsgi:application
        socket={socket}:0
        processes={workers}
        master=1
        buffer-size=65535
        env=BATTERIES={batteries}
        env=APPLICATION_SETTINGS={app_settings}
        env=LEAF_SETTINGS={leaf_settings}
        logformat={logformat}
        """.format(
            chdir=self.chdir,
            socket=self.host,
            app_settings=json.dumps(self.settings),
            batteries=json.dumps(self.batteries),
            leaf_settings=json.dumps(leaf_settings),
            logformat=json.dumps(logs_format),
            workers=self.workers
        )
        if self.threads:
            config += "enable-threads=1\n"
        address_list = self.address if type(self.address) == list else [self.address]

        for router in self.fastrouters:
            for address in address_list:
                config += "subscribe-to={0}:{1},5,SHA1:{2}\n".format(
                    router,
                    address, self.keyfile)

        return config

    def run_tasks(self, tasks):
        for task, args in tasks:
            task(*args)

    #==============
    # Триггеры
    #==============

    def before_start(self):
        triggers = self.type.get("triggers", {})
        cmds = triggers.get("before_start", [])

        my_env = os.environ
        my_env["APPLICATION_SETTINGS"] = json.dumps(self.settings)
        my_env["BATTERIES"] = json.dumps(self.batteries)

        for cmd in cmds:
            process = subprocess.Popen(
                cmd.split(),
                env=my_env,
                shell=False,
                stderr=subprocess.PIPE,
                stdout=subprocess.PIPE
                )
            process.wait()
            logs = ""
            for line in iter(process.stderr.readline, ''):
                logs += line + "\n"
            for line in iter(process.stdout.readline, ''):
                logs += line + "\n"

            self.logger.insert({
                "component_name": self.component,
                "component_type": "branch",
                "log_source": self.name,
                "log_type": "leaf.before_start",
                "content": logs,
                "added": datetime.datetime.now()
            })
