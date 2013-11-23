# -*- coding: utf-8 -*-
from __future__ import print_function
import tornado.web
import os
import psutil

class Owl(tornado.web.Application):
    def __init__(self, settings_dict, **settings):
        super(Owl, self).__init__(**settings)
        self.settings = settings_dict

    def process_message(self, message):
        function = message.get('function', None)
        if function == "status_report":
            response = self.status_report()

        if function is None:
            response = {
                "result": "failure",
                "message": "No function or unknown one called"
            }
        return response

    def status_report(self):
        # Память
        mem = psutil.virtual_memory()
        swap = psutil.swap_memory()
        # Нагрузка
        load_1, load_5, load_15 = os.getloadavg()
        # Аптайм
        try:
            f = open( "/proc/uptime" )
            contents = f.read().split()
            f.close()

            total_seconds = float(contents[0])
     
            MINUTE  = 60
            HOUR    = MINUTE * 60
            DAY     = HOUR * 24
         
            days    = int( total_seconds / DAY )
            hours   = int( ( total_seconds % DAY ) / HOUR )
            minutes = int( ( total_seconds % HOUR ) / MINUTE )
            seconds = int( total_seconds % MINUTE )
        except:
            days    = 0
            hours   = 0
            minutes = 0
            seconds = 0

        measurements = {
            "mem_total":      mem.total/(1024*1024),
            "mem_used":       (mem.used - mem.buffers - mem.cached)/(1024*1024),
            "mem_cached":     (mem.buffers + mem.cached)/(1024*1024),
            "mem_free":       mem.free/(1024*1024),
            "swap_total":     swap.total/(1024*1024),
            "swap_used":      swap.used/(1024*1024),
            "swap_free":      swap.free/(1024*1024),
            "load_1":         load_1,
            "load_5":         load_5,
            "load_15":        load_15,
            "uptime_days":    days,
            "uptime_hours":   hours,
            "uptime_minutes": minutes,
            "uptime_seconds": seconds
        }
        return {
            "result":       "success",
            "message":      "Working well",
            "role":         "owl",
            "mesaurements": measurements
        }

