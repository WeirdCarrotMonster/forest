# -*- coding: utf-8 -*- 
import subprocess

class Leaf():
	def __init__(self):
		self.pid = 0

	def start(self, name, env, manage, pidfile):
		cmd = [
			self.python_executable,
			manage,
			"runfcgi",
			"method=" + self.fcgi_method,
			"host=" + self.fcgi_host,
			"port=" + str(self.fcgi_port),
			"pidfile=" + pidfile
		]
		process = subprocess.call(cmd)
		pidfile_result = open(pidfile, 'r')
		self.pid = int(pidfile_result.read().strip())
		pidfile_result.close()

	def stop(self):
		subprocess.call(['kill', str(self.pid)])
		self.pid = 0

	python_executable = "python2.7"
	fcgi_method = "threaded"
	fcgi_host = "127.0.0.1"
	fcgi_port = 3000
