# coding=utf-8

from __future__ import unicode_literals, print_function

from tornado import gen
import simplejson as json

from components.api.handler import Handler
from components.common import CustomEncoder
from components.decorators import login_required


class CommonLeafSettingsHandler(Handler):
    @gen.coroutine
    @login_required
    def get(self):
        db = self.application.async_db

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
