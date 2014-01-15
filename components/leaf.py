# -*- coding: utf-8 -*- 
import subprocess
import os
from components.common import log_message
import traceback
import simplejson as json


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

    def init_database(self):
        # Два шага инициализации нового инстанса:
        # syncdb для создания основных таблиц
        # migrate для создания таблиц, управляемых через south
        my_env = os.environ
        my_env["DATABASE_SETTINGS"] = self.launch_env
        my_env["APPLICATION_SETTINGS"] = self.settings
        subprocess.Popen([self.python_executable, self.executable, "syncdb", "--noinput"], env=my_env, shell=False)
        subprocess.Popen([self.python_executable, self.executable, "migrate"], env=my_env, shell=False)

    def update_database(self):
        # Обновляем таблицы через south
        my_env = os.environ
        my_env["DATABASE_SETTINGS"] = self.launch_env
        my_env["APPLICATION_SETTINGS"] = self.settings
        subprocess.Popen([self.python_executable, self.executable, "migrate"], env=my_env, shell=False)

    def mem_usage(self):
        if self.process.poll() == None:
            mem = int(subprocess.check_output(
                [
                    'ps', 
                    '-p', 
                    str(self.process.pid), 
                    '-o', 
                    'rss='])
            )
        else:
            mem = 0
        return mem/1024

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
            "-b=65535"
        ]
        print(' '.join(cmd))
        my_env = os.environ
        my_env["DATABASE_SETTINGS"] = self.launch_env
        my_env["APPLICATION_SETTINGS"] = self.settings
        log_message("Starting leaf {0}".format(self.name), component="Leaf")
        self.process = subprocess.Popen(cmd, env=my_env)
        if self.process.poll() == None:
            log_message("Started leaf {0}".format(self.name), component="Leaf")
        else:
            raise Exception("Launch failed: {0}".format(traceback.format_exc()))
            

    def stop(self):
        log_message("Stopping leaf {0}".format(self.name), component="Leaf")
        self.process.kill()
