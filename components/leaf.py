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


def enqueue_output(out, queue):
    for line in iter(out.readline, b''):
        queue.put(line)
    out.close()


class Leaf():
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
                 leaf_type=None
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
        p = subprocess.Popen(
            [self.python_executable, self.executable, "syncdb", "--noinput"],
            env=my_env,
            shell=False,
            stderr=subprocess.PIPE,
            stdout=subprocess.PIPE)
        p.wait()
        p = subprocess.Popen(
            [self.python_executable, self.executable, "migrate"],
            env=my_env,
            shell=False,
            stderr=subprocess.PIPE,
            stdout=subprocess.PIPE)
        p.wait()

    def update_database(self):
        # Обновляем таблицы через south
        my_env = os.environ
        my_env["DATABASE_SETTINGS"] = json.dumps(self.launch_env)
        my_env["APPLICATION_SETTINGS"] = json.dumps(self.settings)
        subprocess.Popen(
            [self.python_executable, self.executable, "migrate"],
            env=my_env,
            shell=False,
            stderr=subprocess.PIPE,
            stdout=subprocess.PIPE)

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
        minutes = time_delta.days * 24 * 60 + time_delta.seconds / float(60)
        if minutes > 5:
            self._last_req_count = float(count) / float(minutes)
        else:
            self._last_req_count = \
                (count + self._last_req_count * (5 - minutes))/float(5)

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
            "--socket={0}:0".format(self.host),
            "--processes=4",
            "--master",
            "--buffer-size=65535"
        ]
        my_env = os.environ
        my_env["DATABASE_SETTINGS"] = json.dumps(self.launch_env)
        my_env["APPLICATION_SETTINGS"] = json.dumps(self.settings)

        address = []
        if type(self.address) in [str, unicode]:
            address.append(self.address)
        elif type(self.address) == list:
            for addr in self.address:
                address.append(addr)

        for router in self.fastrouters:
            for addr in address:
                cmd.append(
                    "--subscribe-to={0}:{1},5,SHA1:{2}".format(
                    router,
                    addr, self.keyfile))

        if self.static:
            cmd.append("--static-map={0}={1}".format(
                self.static["mount"],
                os.path.join(self.chdir, self.static["dir"])
            ))

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

    def graceful_restart(self):
        self.process.send_signal(signal.SIGHUP)

    def restart(self):
        self.stop()
        self.start()

    def get_logs(self):
        self.update_logs_req_count()
        return self.logs

    def do_update_routine(self):
        self.update_database()
        self.graceful_restart()

    def status(self):
        if self.process is None:
            return "stopped"
        elif self.process.poll != 0:
            return "killed"
        else:
            return "running"
