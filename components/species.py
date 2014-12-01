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


class Species(object):
    """
    Класс, представляющий вид листа - совокупность исходного кода и виртуального
    окружения python
    """
    def __init__(self, directory, _id, name, url, ready_callback, modified, triggers=None, interpreter=None, **kwargs):
        self.directory = directory
        self.specie_id = _id
        self.specie_path = os.path.join(self.directory, str(self.specie_id))
        self.interpreter = interpreter if interpreter in ["python2", "python3"] else "python2"
        self.url = url
        self.name = name
        self.triggers = triggers or {}
        self._environment = os.path.join(self.specie_path, "env")
        self._path = os.path.join(self.specie_path, "src")
        self.ready_callback = ready_callback
        self.modified = modified

        self.is_ready = self.modified == self.metadata.get("modified")

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
            log_message("Creating directory for {}".format(self.name), component="Specie")
            os.makedirs(self.specie_path)

        if self.modified != self.metadata.get("modified"):
            if os.path.exists(self._path):
                shutil.rmtree(self._path)
            log_message("Initializing sources for {}".format(self.name), component="Specie")
            result, error = yield self.run_in_env(
                [
                    "git",
                    "clone",
                    "--depth", "1",
                    self.url,
                    self._path
                ],
                apply_env=False
            )

            if os.path.exists(self._environment):
                shutil.rmtree(self._environment)
            log_message("Creating virtualenv for specie {}".format(self.name), component="Specie")
            result, error = yield self.run_in_env(
                [
                    "virtualenv",
                    "--python=%s" % self.python_version,
                    self._environment
                ],
                apply_env=False
            )

            log_message("Installing virtualenv requirements for {}".format(self.name), component="Specie")

            result, error = yield self.run_in_env(
                [
                    os.path.join(self._environment, "bin/pip"),
                    "install",
                    "-r",
                    os.path.join(self._path, "requirements.txt"),
                    "--upgrade"
                ]
            )
            metadata = self.metadata
            metadata["modified"] = self.modified
            self.metadata = metadata
            self.is_ready = True
            log_message("Done initializing {}".format(self.name), component="Specie")
            self.ready_callback(self)

    @coroutine
    def run_in_env(self, cmd, stdin_data=None, env=None, apply_env=True, path=None):
        """
        Wrapper around subprocess call using Tornado's Subprocess class.
        https://gist.github.com/FZambia/5756470
        """
        cmd = shlex.split(cmd) if type(cmd) != list else cmd
        process_env = os.environ.copy()
        if apply_env:
            process_env["PATH"] = os.path.join(self._environment, "bin") + ":" + process_env.get("PATH", "")
            process_env["VIRTUAL_ENV"] = self._environment

        if env:
            process_env.update(env)

        if not path:
            path = self.specie_path

        sub_process = tornado.process.Subprocess(
            cmd,
            env=process_env,
            cwd=path,
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
    def src_path(self):
        return self._path

    @property
    def path(self):
        return self.specie_path

    @property
    def environment(self):
        return self._environment

    @property
    def id(self):
        return self.specie_id