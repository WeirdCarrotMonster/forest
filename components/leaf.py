# -*- coding: utf-8 -*-
import subprocess
import os
import signal
from components.common import log_message
import traceback
import simplejson as json
from threading import Thread
from Queue import Queue, Empty
import datetime
from time import sleep


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
                 chdir=None,
                 env=None,
                 settings=None,
                 fastrouters=None,
                 keyfile=None,
                 address="",
                 static=None,
                 leaf_type=None,
                 emperor=None,
                 logger=None,
                 component=None
                 ):
        self.name = name
        self.python_executable = python_executable
        self.host = host
        self.chdir = chdir
        self.executable = executable
        self.launch_env = env or {}
        self.settings = settings or {}
        self.process = None
        self.fastrouters = fastrouters or []
        self.keyfile = keyfile
        self.address = address
        self.static = static
        self.type = leaf_type
        self.emperor = emperor
        self.logger = logger
        self.component = component

        self._thread = None
        self._queue = None
        self.logs = []

        self._last_req_measurement = datetime.datetime.now()
        self._last_req_count = 0

    def init_database(self):
        # Инициализация таблиц через syncdb
        my_env = os.environ
        my_env["DATABASE_SETTINGS"] = json.dumps(self.launch_env)
        my_env["APPLICATION_SETTINGS"] = json.dumps(self.settings)
        logs = ""
        proc = subprocess.Popen(
            [self.python_executable, self.executable, "syncdb", "--noinput"],
            env=my_env,
            shell=False,
            stderr=subprocess.PIPE,
            stdout=subprocess.PIPE)
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
        proc = subprocess.Popen(
            [self.python_executable, self.executable, "migrate"],
            env=my_env,
            shell=False,
            stderr=subprocess.PIPE,
            stdout=subprocess.PIPE)
        proc.wait()
        logs = ""
        for line in iter(proc.stderr.readline, ''):
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
            "wid": "%(name)"
        }
        config = """[uwsgi]\nchdir={chdir}\nmodule=wsgi:application\nsocket={socket}:0\nprocesses=4\nmaster=1\nbuffer-size=65535\nenv=DATABASE_SETTINGS={db_settings}\nenv=APPLICATION_SETTINGS={app_settings}\nlogformat={logformat}\n""".format(
            chdir=self.chdir, 
            socket=self.host,
            db_settings=json.dumps(self.launch_env),
            app_settings=json.dumps(self.settings),
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
        for task in tasks:
            task()

    def start(self):
        self.emperor.send_multipart([
            bytes('touch'),
            bytes('{}.ini'.format(self.name)),
            bytes(self.get_config())
        ])

    def stop(self):
        self.emperor.send_multipart([
            bytes('destroy'),
            bytes('{}.ini'.format(self.name))
        ])

    def restart(self):
        self.stop()
        sleep(5)
        self.start()