# -*- coding: utf-8 -*- 
import subprocess
import os
from components.common import log_message


class Leaf():
    def __init__(self,
                 name=None,
                 python_executable="python2.7",
                 fcgi_method="threaded",
                 fcgi_host="127.0.0.1",
                 fcgi_port=3000,
                 pidfile=None,
                 executable=None,
                 env=""
                 ):
        self.name = name
        self.python_executable = python_executable
        self.fcgi_method = fcgi_method
        self.fcgi_host = fcgi_host
        self.fcgi_port = fcgi_port
        self.pidfile = pidfile
        self.executable = executable
        self.launch_env = env
        self.pid = 0

    def prepare_database(self):
        cmd = [
            self.python_executable,
            self.executable,
            "syncdb",
            "--noinput"
        ]
        my_env = os.environ
        my_env["DATABASE_SETTINGS"] = self.launch_env
        subprocess.Popen(cmd, env=my_env, shell=False)

    def start(self):
        # TODO: кидать exception, если присутствуют не все настройки
        # что-то через not all(..)
        cmd = [
            self.python_executable,
            self.executable,
            "runfcgi",
            "method=" + self.fcgi_method,
            "host=" + self.fcgi_host,
            "port=" + str(self.fcgi_port),
            "pidfile=" + self.pidfile
        ]
        my_env = os.environ
        my_env["DATABASE_SETTINGS"] = self.launch_env
        log_message("Starting leaf {0}".format(self.name))
        subprocess.call(cmd, env=my_env)
        log_message("Started leaf {0}".format(self.name))
        try:
            pidfile_result = open(self.pidfile, 'r')
            self.pid = int(pidfile_result.read().strip())
            pidfile_result.close()
        except Exception, e:
            raise Exception("Launch failed: {0}".format(e))

    def stop(self):
        log_message("Stopping leaf {0}".format(self.name))
        subprocess.call(['kill', str(self.pid)])
        os.remove(self.pidfile)
        self.pid = 0