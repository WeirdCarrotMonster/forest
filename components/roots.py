# -*- coding: utf-8 -*-
from __future__ import print_function
import MySQLdb
import string
import random
from components.common import log_message, get_default_database
import components.batteries


class Roots():

    def __init__(self, settings):
        self.settings = settings
        self.update_state()

        self.functions = {
            "roots.update_state": self.update_state
        }

    def update_state(self):
        """
        Метод подготовки баз данных (батареек)
        Поочередно проверяет в базе наличие листов, у которых нужно выполнить
        подготовку батареек разного типа - mysql, mongo, etc (в будущем)

        :rtype : dict
        :return: Результат подготовки баз
        """
        for battery in components.batteries.Battery.__subclasses__():
            battery.prepare(self.settings)

        return {
            "result": "success"
        }
