# -*- coding: utf-8 -*-

from __future__ import print_function, unicode_literals

from datetime import datetime

import bson
from simplejson import JSONEncoder


class LogicError(Exception):
    pass


class CustomEncoder(JSONEncoder):
    def default(self, obj):
        if type(obj) == datetime:
            return obj.isoformat()
        elif type(obj) == bson.objectid.ObjectId:
            return str(obj)
        else:
            return JSONEncoder.default(self, obj)


def log_message(message, component="Forest", end="\n"):
    print("[{0}][{1:8}] {2}".format(datetime.now(), component, message), end=end)
