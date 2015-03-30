# -*- coding: utf-8 -*-
"""
Модуль реализует сущность окружения для запуска листа, отвечающего за
подготовку виртуального окружения питона, обновление репозитория и
автоматическое развертывание
"""

from __future__ import print_function, unicode_literals

import os
from os.path import join
import shutil
import shlex

import tornado
from tornado.gen import coroutine, Task, Return
from simplejson import JSONDecodeError

from forest.components.common import log_message, dump, load


# pylint: disable=W0612,W0613


class Species(object):

    """
    Класс, представляющий вид листа - совокупность исходного кода
    и виртуального окружения python
    """

    class NotDefined(Exception):
        pass

    def __init__(
            self,
            directory,
            _id,
            name,
            url,
            ready_callback,
            modified,
            triggers=None,
            interpreter=None,
            branch="master",
            **kwargs):
        """
        :param directory: Корневая директория вида
        :type directory: str
        :param _id: Уникальный идентификатор вида
        :type _id: ObjectId
        :param name: Человеко-читаемое имя вида
        :type name: str
        :param url: URL исходных кодов приложения
        :type url: str
        :param ready_callback: Функция, выполняемая по завершении инициализации
        :type ready_callback: function
        :param modified: Дата последнего изменения вида
        :type modified: DateTime
        :param triggers: Словарь триггеров, выполняемых при запуске листьев
        :type triggers: dict
        :param interpreter: Используемый интерпретатор python
        :type interpreter: str
        :param branch: Ветвь репозитория (при использовании git)
        :type branch: str
        """
        self.directory = directory
        self.specie_id = _id
        self.interpreter = interpreter if interpreter in ["python2", "python3"] else "python2"
        self.url = url
        self.name = name
        self.branch = branch
        self.triggers = triggers or {}

        if not os.path.exists(self.path):
            os.makedirs(self.path)

        self.ready_callback = ready_callback
        self.modified = modified

        self.__ready__ = self.modified == self.saved_data.get("modified")
        self.update_saved_data()

    @property
    def is_ready(self):
        """Возвращает значение готовности вида
        :returns: Готовность вида
        :rtype: bool
        """
        return self.__ready__

    @is_ready.setter
    def is_ready(self, value):
        """Устанавливает флаг готовности вида
        :param value: Новое значение флага готовности
        :type value: bool
        """
        self.__ready__ = value

    @property
    def python(self):
        """Возвращает версию интерпретатора, на использование которой настроен данный вид
        :returns: Строка с именем исполняемого файла интерпретатора
        :rtype: str
        """
        return "python2"

    @property
    def description(self):
        """Формирует краткое описание вида, достаточное для сравнения объектов.
        :returns: Словарь с кратким описанием
        :rtype dict:
        """
        return {
            "_id": self.id,
            "modified": self.modified
        }

    @property
    def saved_data(self):
        """Загружает и возвращает настройки вида, описанные в файле метаданных
        :returns: Словарь с настройками вида
        :rtype: dict
        """
        try:
            with open(join(self.path, "metadata.json"), 'r') as f:
                data = load(f)
            return data
        except (IOError, JSONDecodeError):
            return {}

    def update_saved_data(self):
        """Обновляет сохраненные настройки вида актуальными данными
        """
        data = {
            "_id": self.id,
            "name": self.name,
            "url": self.url,
            "modified": self.modified,
            "triggers": self.triggers,
            "interpreter": self.interpreter,
            "branch": self.branch,
        }

        with open(join(self.path, "metadata.json"), 'w') as f:
            dump(data, f)

    @coroutine
    def initialize(self):
        """Инициализирует корневую директорию вида
        """
        if not self.is_ready:
            if os.path.exists(self.src_path):
                shutil.rmtree(self.src_path)
            log_message(
                "Initializing sources for {}".format(self.name),
                component="Species"
            )
            yield self.run_in_env(
                [
                    "git",
                    "clone",
                    "--depth", "1",
                    "--branch", self.branch,
                    self.url,
                    self.src_path
                ],
                apply_env=False
            )

            if os.path.exists(self.environment):
                shutil.rmtree(self.environment)
            log_message(
                "Creating virtualenv for species {}".format(self.name),
                component="Species"
            )

            yield self.run_in_env(
                [
                    "virtualenv",
                    "--python=%s" % self.python,
                    self.environment
                ],
                apply_env=False
            )

            log_message(
                "Installing virtualenv requirements for {}".format(self.name),
                component="Species"
            )

            yield self.run_in_env(
                [
                    os.path.join(self.environment, "bin/pip"),
                    "install",
                    "-r",
                    os.path.join(self.src_path, "requirements.txt"),
                    "--upgrade"
                ]
            )

            self.is_ready = True
            log_message(
                "Done initializing {}".format(self.name),
                component="Species"
            )
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
            process_env["PATH"] = join(self.environment, "bin") + ":" + process_env.get("PATH", "")
            process_env["VIRTUAL_ENV"] = self.environment

        if env:
            process_env.update(env)

        if not path:
            path = self.path

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
    def path(self):
        """Возвращает полный путь к корневой директории вида
        :returns: Полный путь к корневой директории вида
        :rtype: str
        """
        return os.path.join(self.directory, str(self.specie_id))

    @property
    def src_path(self):
        """Путь к директории с исходными кодами вида (обычно root/src)
        :returns: Полынй путь к директории исходных кодов
        :rtype: str
        """
        return os.path.join(self.path, "src")

    @property
    def environment(self):
        """Возвращает полный путь к директории виртуального окржения вида (обычно root/env)
        :returns: Полный путь к директории виртуального окружения
        :rtype: str
        """
        return os.path.join(self.path, "env")

    @property
    def id(self):
        """Уникальный идентификатор вида
        :returns: Идентификатор вида
        :rtype: ObjectId
        """
        return self.specie_id
