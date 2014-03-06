# -*- coding: utf-8 -*-
import subprocess
import os
import signal
from components.common import log_message
import traceback
import simplejson as json
from threading import Thread
from Queue import Queue
import datetime


def enqueue_output(out, queue):
    for line in iter(out.readline, b''):
        queue.put(line)
    out.close()


class Leaf():
    def __init__(self,
                 name=None,
                 python_executable="python2.7",
                 host="127.0.0.1",
                 port=3000,
                 executable=None,
                 chdir=None,
                 env={},
                 settings={}
                 ):
        self.name = name
        self.python_executable = python_executable
        self.host = host
        self.port = port
        self.chdir = chdir
        self.executable = executable
        self.launch_env = env
        self.settings = settings
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
        my_env["DATABASE_SETTINGS"] = json.dumps(self.launch_env)
        my_env["APPLICATION_SETTINGS"] = json.dumps(self.settings)
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
        my_env["DATABASE_SETTINGS"] = json.dumps(self.launch_env)
        my_env["APPLICATION_SETTINGS"] = json.dumps(self.settings)
        subprocess.Popen(
            [self.python_executable, self.executable, "migrate"],
            env=my_env,
            shell=False)

    def set_settings(self, settings):
        self.settings = settings

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
        # Старая логика - говно
        # TODO: написать нормальный анализ
        return 0

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
            "--fastcgi-socket={0}:{1}".format(self.host, self.port),
            "--processes=4",
            "--master",
            "--buffer-size=65535"
        ]
        my_env = os.environ
        my_env["DATABASE_SETTINGS"] = json.dumps(self.launch_env)
        my_env["APPLICATION_SETTINGS"] = json.dumps(self.settings)
        log_message("Starting leaf {0}".format(self.name), component="Leaf")

        self.process = subprocess.Popen(
            cmd,
            env=my_env,
            stderr=subprocess.PIPE,
            bufsize=1,
            close_fds=True
        )
        if self.process.poll() is None:
            self._queue = Queue()
            self._thread = Thread(
                target=enqueue_output,
                args=(self.process.stderr, self._queue)
            )
            self._thread.daemon = True
            self._thread.start()
        else:
            raise Exception("Launch failed: {0}".format(traceback.format_exc()))

    def stop(self):
        log_message("Stopping leaf {0}".format(self.name), component="Leaf")
        try:
            self.process.send_signal(signal.SIGINT)
            self.process.wait()
            self.process = None
            del self._thread
        except OSError:
            pass

    def restart(self):
        self.process.send_signal(signal.SIGHUP)

    def get_logs(self):
        self.update_logs_req_count()
        return self.logs

    def do_update_routine(self):
        self.update_database()
        self.restart()

    def status(self):
        if self.process is None:
            return "stopped"
        elif self.process.poll != 0:
            return "killed"
        else:
            return "running"
