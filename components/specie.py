# -*- coding: utf-8 -*-
"""
Модуль реализует сущность окружения для запуска листа, отвечающего за
подготовку виртуального окружения питона, обновление репозитория и
автоматическое развертывание
"""
from __future__ import print_function, unicode_literals

import os
import subprocess

from components.common import CallbackThread as Thread
from components.common import log_message


class Specie():
    def __init__(self, directory, specie_id, name, url, last_update, triggers):
        self.directory = directory
        self.specie_id = specie_id
        self.specie_path = os.path.join(self.directory, str(self.specie_id))
        self.url = url
        self.name = name
        self.triggers = triggers
        self.last_update = last_update
        self._environment = os.path.join(self.specie_path, "env")
        self._path = os.path.join(self.specie_path, "src")
        self.is_ready = False

    def initialize(self):
        if not os.path.exists(self.specie_path):
            log_message("Creating directory for {}".format(self.name), component="Specie")
            os.makedirs(self.specie_path)
        if not os.path.exists(self._path):
            log_message("Cloning repository for {}".format(self.name), component="Specie")
            process = subprocess.Popen(
                [
                    "git",
                    "clone",
                    self.url,
                    self._path
                ],
                stderr=subprocess.PIPE,
                stdout=subprocess.PIPE
            )
            process.wait()
        else:  # TODO: условие обновления - ревизия
            log_message("Updating repository for specie {}".format(self.name), component="Specie")
            process = subprocess.Popen(
                [
                    "git",
                    "-C",
                    self._path,
                    "pull"
                ],
                stderr=subprocess.PIPE,
                stdout=subprocess.PIPE
            )
            process.wait()

        if not os.path.exists(self._environment):
            log_message("Creating virtualenv for specie {}".format(self.name), component="Specie")
            process = subprocess.Popen(
                [
                    "virtualenv",
                    "--python=python2.7",
                    self._environment
                ],
                stderr=subprocess.PIPE,
                stdout=subprocess.PIPE
            )
            process.wait()
        log_message("Installing virtualenv requirements for {}".format(self.name), component="Specie")
        process = subprocess.Popen(
            [
                os.path.join(self._environment, "bin/pip"),
                "install",
                "-r",
                os.path.join(self._path, "requirements.txt")
            ],
            stderr=subprocess.PIPE,
            stdout=subprocess.PIPE
        )
        process.wait()

    @property
    def path(self):
        return self._path

    @property
    def environment(self):
        return self._environment

    @property
    def id(self):
        return self.specie_id
