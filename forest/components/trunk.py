# coding=utf-8
"""Модуль, описывающий класс корневого объекта леса.

Корневой объект - синглтон, поверх которого инициализируются все дополнительные
модули леса. Название 'Trunk' он получил из-за того, что по логике работы именно
к нему крепятся корни ('Roots'), ветки ('Branch') и воздух ('Air', это уже не
так логично, но мне всё равно).
"""

import os

import tornado.httpclient
import tornado.template
import tornado.web

from forest.components.emperor import Emperor
from forest.components.database import get_default_database


class Trunk(tornado.web.Application):

    """Класс корневого объекта леса.

    В аттрибутах класса хранятся все компоненты, с которыми инициализирована
    нода леса, а так же подключения к базе (при их наличии).
    """

    def __init__(self, settings, **kwargs):
        """Инициализируется данными из словаря настроек.

        :param settings: Словарь корневых настроек ноды
        :type settings: dict
        """
        super(Trunk, self).__init__(**kwargs)
        self.settings["cookie_secret"] = "asdasd"
        self.name = settings["name"]
        self.root = settings["root"]
        self.host = settings["host"]
        self.secret = settings["secret"]
        self.emperor_dir = settings.get("emperor", os.path.join(self.forest_root, "emperor"))

        self.database = settings.get("db")
        if self.database:
            self.async_db = get_default_database(self.database, async=True)
            self.sync_db = get_default_database(self.database)

        self.branch = None
        self.roots = None
        self.druid = None
        self.air = None

        self.emperor = Emperor(self.emperor_dir)

    @property
    def id(self):
        """Возвращает уникальный идентификатор ноды леса.

        :returns: Уникальный идентификатор ноды
        :rtype: str
        """
        return self.name

    @property
    def forest_root(self):
        """Возвращает путь к корневой рабочей директории леса.

        :return: Полный путь к рабочей директории
        :rtype: str
        """
        return self.root

    def cleanup(self):
        """Останавливает ноду леса."""
        self.emperor.stop()
