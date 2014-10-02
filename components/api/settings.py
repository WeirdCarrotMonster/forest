# coding=utf-8

from __future__ import unicode_literals, print_function

from tornado import gen
from tornado.web import asynchronous
import simplejson as json
from components.api.handler import Handler

from components.common import CustomEncoder
from components.database import get_default_database
from components.decorators import login_required


class CommonLeafSettingsHandler(Handler):
    @asynchronous
    @gen.engine
    @login_required
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