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
                 python_executable="python2.7",
                 host="127.0.0.1",
                 executable=None,
                 path=None,
                 env=None,
                 settings=None,
                 fastrouters=None,
                 keyfile=None,
                 address="",
                 leaf_type=None,
                 logger=None,
                 component=None,
                 batteries=None
                 ):
        self.name = name
        self.python_executable = python_executable
        self.host = host
        self.chdir = path
        self.executable = executable
        self.launch_env = env or {}
        self.settings = settings or {}
        self.process = None
        self.fastrouters = fastrouters or []
        self.keyfile = keyfile
        self.address = address
        self.type = leaf_type
        self.logger = logger
        self.component = component
        self.batteries = batteries

        self._thread = None
        self._queue = None
        self.logs = []

        self._last_req_measurement = datetime.datetime.now()
        self._last_req_count = 0

    def __ne__(self, other):
        r1 = self.address == other.address
        r2 = self.settings == other.settings
        r3 = self.launch_env.get("db_pass") == other.launch_env.get("db_pass")
        r4 = self.launch_env.get("db_name") == other.launch_env.get("db_name")
        r5 = self.launch_env.get("db_user") == other.launch_env.get("db_user")
        if not all([r1, r2, r3, r4, r5]):
            return True
        return False

    def init_database(self):
        # Инициализация таблиц через syncdb
        my_env = os.environ
        my_env["DATABASE_SETTINGS"] = json.dumps(self.launch_env)
        my_env["APPLICATION_SETTINGS"] = json.dumps(self.settings)
        my_env["BATTERIES"] = json.dumps(self.batteries)
        logs = ""
        proc = subprocess.Popen(
            [self.python_executable, self.executable, "syncdb", "--noinput"],
            env=my_env,
            shell=False,
            stderr=subprocess.PIPE,
            stdout=subprocess.PIPE
            )
        proc.wait()
        for line in iter(proc.stdout.readline, ''):
            logs += line + "\n"
        for line in iter(proc.stderr.readline, ''):
            logs += line + "\n"

        self.logger.insert({
            "component_name": self.component,
            "component_type": "branch",
            "log_source": self.name,
            "log_type": "leaf.syncdb",
            "content": logs,
            "added": datetime.datetime.now()
        })

    def update_database(self):
        # Обновление таблицы через south
        my_env = os.environ
        my_env["DATABASE_SETTINGS"] = json.dumps(self.launch_env)
        my_env["APPLICATION_SETTINGS"] = json.dumps(self.settings)
        my_env["BATTERIES"] = json.dumps(self.batteries)
        proc = subprocess.Popen(
            [self.python_executable, self.executable, "migrate", "--noinput"],
            env=my_env,
            shell=False,
            stderr=subprocess.PIPE,
            stdout=subprocess.PIPE
            )
        proc.wait()
        logs = ""
        for line in iter(proc.stderr.readline, ''):
            logs += line + "\n"
        for line in iter(proc.stdout.readline, ''):
            logs += line + "\n"

        self.logger.insert({
            "component_name": self.component,
            "component_type": "branch",
            "log_source": self.name,
            "log_type": "leaf.migrate",
            "content": logs,
            "added": datetime.datetime.now()
        })

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
            "static_url": "/static/{0}/".format(self.type)
        }

        config = """[uwsgi]\nchdir={chdir}\nhearthbeat=10\nmodule=wsgi:application\nsocket={socket}:0\nprocesses=4\nmaster=1\nbuffer-size=65535\nenv=DATABASE_SETTINGS={db_settings}\nenv=BATTERIES={batteries}\nenv=APPLICATION_SETTINGS={app_settings}\nenv=LEAF_SETTINGS={leaf_settings}\nlogformat={logformat}\n""".format(
            chdir=self.chdir,
            socket=self.host,
            db_settings=json.dumps(self.launch_env),
            app_settings=json.dumps(self.settings),
            batteries=json.dumps(self.batteries),
            leaf_settings=json.dumps(leaf_settings),
            logformat=json.dumps(logs_format)
        )
        address = self.address if type(self.address) == list else [self.address]

        for router in self.fastrouters:
            for addr in address:
                config += "subscribe-to={0}:{1},5,SHA1:{2}\n".format(
                    router,
                    addr, self.keyfile)

        return config

    def run_tasks(self, tasks):
        for task, args in tasks:
            task(*args)
