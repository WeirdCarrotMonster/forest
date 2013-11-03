# -*- coding: utf-8 -*- 
import subprocess
import os


class Leaf():
    def __init__(self,
                 name=None,
                 python_executable="python2.7",
                 fcgi_method="threaded",
                 fcgi_host="127.0.0.1",
                 fcgi_port=3000,
                 pidfile=None,
                 executable=None,
                 env={}
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
        process = subprocess.call(cmd)
        try:
            pidfile_result = open(self.pidfile, 'r')
            self.pid = int(pidfile_result.read().strip())
            pidfile_result.close()
        except:
            raise Exception("Launch failed")

    def stop(self):
        subprocess.call(['kill', str(self.pid)])
        os.remove(self.pidfile)
        self.pid = 0