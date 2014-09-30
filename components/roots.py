# -*- coding: utf-8 -*-
from __future__ import print_function, unicode_literals
from components.database import get_settings_connection_async, get_default_database
import components.batteries


class Roots():

    def __init__(self, settings, trunk):
        self.settings = settings
        self.trunk = trunk

        self.batteries = []

        trunk = get_default_database(self.trunk.settings, async=True)

        for battery in components.batteries.Battery.__subclasses__():
            battery_name = battery.__name__.lower()

            if battery_name in self.settings:
                self.batteries.append(battery(self.settings[battery.__name__.lower()], trunk))

    def periodic_event(self):
        for battery in self.batteries:
            battery.update()

        return {
            "result": "success"
        }
