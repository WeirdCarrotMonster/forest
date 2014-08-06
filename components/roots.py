# -*- coding: utf-8 -*-
from __future__ import print_function, unicode_literals
import MySQLdb
import string
import random
from components.common import log_message
from components.database import get_default_database
import components.batteries


class Roots():

    def __init__(self, settings, trunk):
        self.settings = settings
        self.trunk = trunk
        self.update_state()

        self.functions = {
            "roots.update_state": self.update_state
        }

    def update_state(self, **kwargs):
        """
        Метод подготовки баз данных (батареек)
        Поочередно проверяет в базе наличие листов, у которых нужно выполнить
        подготовку батареек разного типа - mysql, mongo, etc (в будущем)

        :rtype : dict
        :return: Результат подготовки баз
        """
        log_message("Triggering update", component="Roots")

        to_prepare = []
        for battery in components.batteries.Battery.__subclasses__():
            battery_name = battery.__name__.lower()
            if battery_name in self.settings:
                to_prepare.append(battery)

        if not to_prepare:
            log_message(
                "No batteries to prepare",
                component="Roots"
            )
        else:
            log_message(
                "Preparing batteries: {}".format(", ".join(b.__name__.lower() for b in to_prepare)),
                component="Roots"
            )

        trunk = get_default_database(self.trunk.settings)

        for battery in to_prepare:
            battery.prepare(self.settings[battery.__name__.lower()], trunk)

        return {
            "result": "success"
        }
