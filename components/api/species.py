# coding=utf-8

from __future__ import unicode_literals, print_function

from tornado import gen, web
from tornado.web import asynchronous
import simplejson as json

from components.common import CustomEncoder
from components.database import get_default_database
from components.decorators import login_required


class SpeciesHandler(web.RequestHandler):
    @asynchronous
    @gen.engine
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