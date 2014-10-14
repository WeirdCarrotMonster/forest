# coding=utf-8

from __future__ import unicode_literals, print_function
from datetime import datetime

from tornado import gen
import simplejson as json
from bson import ObjectId

from components.api.handler import Handler
from components.common import CustomEncoder
from components.database import get_default_database
from components.decorators import login_required


class SpeciesHandler(Handler):
    @gen.coroutine
    @login_required
    def get(self):
        db = get_default_database(self.application.settings, async=True)
        cursor = db.species.find()

        self.write("[")

        beginning = True
        while (yield cursor.fetch_next):
            document = cursor.next_object()
            if beginning:
                beginning = False
            else:
                self.write(",")
            self.write(json.dumps(document, cls=CustomEncoder))
        self.finish("]")


class SpecieHandler(Handler):
    @gen.coroutine
    @login_required
    def patch(self, _id):
        data = {"modified": datetime.now()}
        db = get_default_database(self.application.settings, async=True)
        result = yield db.species.find_and_modify(
            {"_id": ObjectId(_id)},
            {"$set": data},
            new=True
        )
        self.finish(json.dumps(result, cls=CustomEncoder))