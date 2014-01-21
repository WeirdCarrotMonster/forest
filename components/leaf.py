# -*- coding: utf-8 -*-
import subprocess
import os
import sys
from components.common import log_message
import traceback
import simplejson as json
from threading import Thread
from Queue import Queue, Empty
import datetime


def enqueue_output(out, queue):
    for line in iter(out.readline, b''):
        queue.put(line)
    out.close()


class Leaf():
    def __init__(self,
                 name=None,
                 python_executable="python2.7",
                 fcgi_method="threaded",
                 fcgi_host="127.0.0.1",
                 fcgi_port=3000,
                 pidfile=None,
                 logfile=None,
                 executable=None,
                 chdir=None,
                 env={},
                 settings={}
                 ):
        self.name = name
        self.python_executable = python_executable
        self.fcgi_method = fcgi_method
        self.fcgi_host = fcgi_host
        self.fcgi_port = fcgi_port
        self.pidfile = pidfile
        self.logfile = logfile
        self.chdir = chdir
        self.executable = executable
        self.launch_env = json.dumps(env)
        self.settings = json.dumps(settings)
        self.pid = 0
        self.process = None

        self._thread = None
        self._queue = None
        self.logs = []

        self._last_req_measurement = datetime.datetime.now()
        self._last_req_count = 0

    def init_database(self):
        # Два шага инициализации нового инстанса:
        # syncdb для создания основных таблиц
        # migrate для создания таблиц, управляемых через south
        my_env = os.environ
        my_env["DATABASE_SETTINGS"] = self.launch_env
        my_env["APPLICATION_SETTINGS"] = self.settings
        subprocess.Popen(
            [self.python_executable, self.executable, "syncdb", "--noinput"],
            env=my_env,
            shell=False)
        subprocess.Popen(
            [self.python_executable, self.executable, "migrate"],
            env=my_env,
            shell=False)

    def update_database(self):
        # Обновляем таблицы через south
        my_env = os.environ
        my_env["DATABASE_SETTINGS"] = self.launch_env
        my_env["APPLICATION_SETTINGS"] = self.settings
        subprocess.Popen(
            [self.python_executable, self.executable, "migrate"],
            env=my_env,
            shell=False)

    def set_settings(self, settings):
        self.settings = json.dumps(settings)

    def mem_usage(self):
        if self.process.poll() is None:
            mem = int(subprocess.check_output(
                [
                    'ps',
                    '-p',
                    str(self.process.pid),
                    '-o',
                    'rss='
                ])
            )
        else:
            mem = 0
        return mem/1024

    def update_logs_req_count(self):
        count = 0
        try:
            while True:
                line = self._queue.get_nowait()
                self.logs.append(line)
                count += 1
        except Empty:
            pass
        measurement_time = datetime.datetime.now()
        time_delta = measurement_time - self._last_req_measurement
        seconds = time_delta.days * 24 * 60 * 60 + time_delta.seconds  # С гарантией
        if seconds > 300:
            self._last_req_count = float(count) / float(seconds)
        else:
            self._last_req_count = (count + self._last_req_count * (300 - seconds))/float(300)

    def req_per_second(self):
        self.update_logs_req_count()
        return self._last_req_count

    def start(self):
        # TODO: кидать exception, если присутствуют не все настройки
        # что-то через not all(..)
        cmd = [
            "uwsgi",
            "--chdir=" + self.chdir,
            "--module=wsgi:application",
            "--master",
            "--fastcgi-socket={0}:{1}".format(self.fcgi_host, self.fcgi_port),
            "--processes=4",
            "--buffer-size=65535"
        ]
        print(' '.join(cmd))
        my_env = os.environ
        my_env["DATABASE_SETTINGS"] = self.launch_env
        my_env["APPLICATION_SETTINGS"] = self.settings
        log_message("Starting leaf {0}".format(self.name), component="Leaf")

        self.process = subprocess.Popen(cmd, env=my_env, stderr=subprocess.PIPE, bufsize=1, close_fds=True)
        if self.process.poll() is None:
            log_message("Started leaf {0}".format(self.name), component="Leaf")
            self._queue = Queue()
            self._thread = Thread(target=enqueue_output, args=(self.process.stderr, self._queue))
            self._thread.daemon = True
            self._thread.start()
        else:
            raise Exception("Launch failed: {0}".format(traceback.format_exc()))

    def stop(self):
        log_message("Stopping leaf {0}".format(self.name), component="Leaf")
        try:
            self.process.send_signal(subprocess.signal.SIGINT)
            self.process.wait()
        except OSError:
            pass

    def get_logs(self):
        self.update_logs_req_count()
        return self.logs
