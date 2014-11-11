# -*- coding: utf-8 -*-
"""
Модуль реализует сущность окружения для запуска листа, отвечающего за
подготовку виртуального окружения питона, обновление репозитория и
автоматическое развертывание
"""
from __future__ import print_function, unicode_literals

import os
import shutil
import shlex
from bson import ObjectId

import dateutil.parser
import tornado
from tornado.gen import coroutine, Task, Return
from tornado.process import Subprocess
import simplejson as json

from components.common import log_message, CustomEncoder


class Specie(object):
    """
    Класс, представляющий вид листа - совокупность исходного кода и виртуального
    окружения python
    """
    def __init__(self, directory, specie_id, name, url, triggers, ready_callback, modified, interpreter):
        self.directory = directory
        self.specie_id = specie_id
        self.specie_path = os.path.join(self.directory, str(self.specie_id))
        self.interpreter = interpreter if interpreter in ["python2", "python3"] else "python2"
        self.url = url
        self.name = name
        self.triggers = triggers
        self._environment = os.path.join(self.specie_path, "env")
        self._path = os.path.join(self.specie_path, "src")
        self.is_ready = False
        self.ready_callback = ready_callback
        self.modified = modified

    @property
    def python_version(self):
        return "python2"

    @property
    def metadata(self):
        try:
            with open(os.path.join(self.specie_path, "metadata.json"), 'r') as f:
                data = json.loads(f.read())

                for key, value in data.items():
                    try:
                        data[key] = ObjectId(value)
                    except ValueError:
                        pass
            return data
        except:
            return {}

    @metadata.setter
    def metadata(self, value):
        data = json.dumps(value, cls=CustomEncoder)
        with open(os.path.join(self.specie_path, "metadata.json"), 'w') as f:
            f.write(data)

    @coroutine
    def initialize(self):
        if not os.path.exists(self.specie_path):
            log_message(
                "Creating directory for {}".format(self.name),
                component="Specie"
            )
            os.makedirs(self.specie_path)
        self.initialize_sources()

    def initialize_sources(self):
        last_updated = self.metadata.get("modified")
        if not os.path.exists(self._path) or not last_updated or last_updated < self.modified:
            if os.path.exists(self._path):
                shutil.rmtree(self._path)

            log_message(
                "Initializing sources for {}".format(self.name),
                component="Specie"
            )

            process = Subprocess(
                [
                    "git",
                    "clone",
                    "--depth", "1",
                    self.url,
                    self._path
                ],
                stderr=tornado.process.Subprocess.STREAM,
                stdout=tornado.process.Subprocess.STREAM
            )
            process.set_exit_callback(self.initialize_environ)
            metadata = self.metadata
            metadata["modified"] = self.modified
            self.metadata = metadata
        else:
            self.initialization_finished()

    @coroutine
    def initialize_environ(self, result):
        if not os.path.exists(self._environment):
            log_message(
                "Creating virtualenv for specie {}".format(self.name),
                component="Specie"
            )
            my_env = os.environ.copy()
            process = Subprocess(
                [
                    "virtualenv",
                    "--python=%s" % self.python_version,
                    self._environment
                ],
                env=my_env,
                stderr=tornado.process.Subprocess.STREAM,
                stdout=tornado.process.Subprocess.STREAM
            )
            process.set_exit_callback(self.install_packages)
        else:
            self.install_packages(0)

    @coroutine
    def install_packages(self, result):
        log_message(
            "Installing virtualenv requirements for {}".format(self.name),
            component="Specie"
        )

        my_env = os.environ.copy()
        process = Subprocess(
            [
                os.path.join(self._environment, "bin/pip"),
                "install",
                "-r",
                os.path.join(self._path, "requirements.txt"),
                "--upgrade"
            ],
            env=my_env,
            stderr=tornado.process.Subprocess.STREAM,
            stdout=tornado.process.Subprocess.STREAM
        )
        process.set_exit_callback(self.initialization_finished)

    def initialization_finished(self, result=None):
        log_message(
            "Done initializing {}".format(self.name),
            component="Specie"
        )
        self.ready_callback(self)

    @coroutine
    def run_in_env(self, cmd, stdin_data=None, env=None):
        """
        Wrapper around subprocess call using Tornado's Subprocess class.
        https://gist.github.com/FZambia/5756470
        """
        cmd = shlex.split(cmd)
        process_env = os.environ.copy()
        process_env["PATH"] = os.path.join(self._environment, "bin") + ":" + process_env.get("PATH", "")
        process_env["VIRTUAL_ENV"] = self._environment

        if env:
            process_env.update(env)

        sub_process = tornado.process.Subprocess(
            cmd,
            env=process_env,
            cwd=self._path,
            stdin=tornado.process.Subprocess.STREAM,
            stdout=tornado.process.Subprocess.STREAM,
            stderr=tornado.process.Subprocess.STREAM
        )

        if stdin_data:
            yield Task(sub_process.stdin.write, stdin_data)
            sub_process.stdin.close()

        result, error = yield [
            Task(sub_process.stdout.read_until_close),
            Task(sub_process.stderr.read_until_close)
        ]

        raise Return((result, error))

    @property
    def path(self):
        return self._path

    @property
    def environment(self):
        return self._environment

    @property
    def id(self):
        return self.specie_id
