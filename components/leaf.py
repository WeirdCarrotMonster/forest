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
    statuses = (
        (0, "Stopped"),
        (1, "Started"),
        (2, "Waiting: trigger before_start"),
        (3, "Waiting: environment")
    )

    def __init__(self,
                 name=None,
                 _id=None,
                 host="127.0.0.1",
                 settings=None,
                 fastrouters=None,
                 keyfile=None,
                 address=None,
                 logger=None,
                 component=None,
                 batteries=None,
                 workers=4,
                 threads=False,
                 specie=None
                 ):
        self.name = name
        self.host = host
        self.specie = specie
        self.settings = settings or {}
        self.process = None
        self.fastrouters = fastrouters or []
        self.keyfile = keyfile
        self.address = address
        self.logger = logger
        self.component = component
        self.batteries = batteries
        self.workers = workers
        self.threads = threads
        self._log_port = None
        self.id = _id

        self._thread = None
        self._queue = None
        self.logs = []

        self._last_req_measurement = datetime.datetime.now()
        self._last_req_count = 0
        self.set_status(0)

    def __ne__(self, other):
        r1 = self.address == other.address
        r2 = self.settings == other.settings
        r3 = self.workers == other.workers
        r4 = self.batteries == other.batteries
        return not all([r1, r2, r3, r4])

    @property
    def log_port(self):
        return self._log_port

    @log_port.setter
    def log_port(self, value):
        self._log_port = value

    def set_status(self, status):
        self.status = self.statuses[status]

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
            "log_source": str(self.id)
        }

        leaf_settings = {
            "static_url": "/static/{0}/".format(self.specie.name)
        }

        config = """
        [uwsgi]
        strict=1
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
        virtualenv={virtualenv}
        static-map=/static={chdir}/static
        req-logger = socket:{logto}
        log-encoder = prefix [Leaf {id}]
        """.format(
            chdir=self.specie.path,
            virtualenv=self.specie.environment,
            socket=self.host,
            app_settings=json.dumps(self.settings),
            batteries=json.dumps(self.batteries),
            leaf_settings=json.dumps(leaf_settings),
            logformat=json.dumps(logs_format),
            logto="127.0.0.1:{}".format(self._log_port),
            workers=self.workers,
            id=self.id
        )
        if self.threads:
            config += "enable-threads=1\n"

        for router in self.fastrouters:
            for address in self.address:
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
        self.set_status(2)
        triggers = self.specie.triggers
        cmds = triggers.get("before_start", [])

        my_env = os.environ.copy()
        my_env["APPLICATION_SETTINGS"] = json.dumps(self.settings)
        my_env["BATTERIES"] = json.dumps(self.batteries)
        my_env["PYTHONHOME"] = self.specie.environment

        for cmd in cmds:
            process = subprocess.Popen(
                cmd.split(),
                env=my_env,
                cwd=self.specie.path,
                shell=False,
                stderr=subprocess.PIPE,
                stdout=subprocess.PIPE
                )
            process.wait()
            logs = ""
            for line in iter(process.stderr.readline, ''):
                logs += line
            for line in iter(process.stdout.readline, ''):
                logs += line

            self.logger.insert({
                "component_name": self.component,
                "component_type": "branch",
                "log_source": self.id,
                "log_type": "leaf.before_start",
                "content": logs,
                "added": datetime.datetime.now()
            })
