# coding=utf-8

from __future__ import unicode_literals, print_function
from datetime import datetime

from tornado import gen, web
from tornado.web import asynchronous
import simplejson as json
from components.common import CustomEncoder
from components.database import get_default_database
from bson import ObjectId


class CommonLeafSettingsHandler(web.RequestHandler):
    @asynchronous
    @gen.engine
    def get(self):
        db = get_default_database(self.application.settings, async=True)

        cursor = db.components.find({"roles.branch": {"$exists": True}})
        branches = yield cursor.to_list(length=100)

        common = {
            "address": {
                "type": "list",
                "elements": "string",
                "verbose": "Адреса"
            },
            "branch": {
                "type": "checkbox_list",
                "values": [{
                    "verbose": branch["name"],
                    "value": branch["_id"]
                } for branch in branches],
                "verbose": "Ветви"
            }
        }

        self.finish(json.dumps(common, cls=CustomEncoder))