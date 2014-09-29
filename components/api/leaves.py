# coding=utf-8

from __future__ import unicode_literals, print_function
from datetime import datetime

from tornado import gen, web
from tornado.web import asynchronous
import simplejson as json
from components.common import CustomEncoder
from components.database import get_default_database
from bson import ObjectId


class LeavesHandler(web.RequestHandler):
    @asynchronous
    @gen.engine
    def get(self):
        db = get_default_database(self.application.settings, async=True)
        cursor = db.leaves.find({}, {'batteries': False, 'settings': False, 'branch': False})
        self.finish(json.dumps(
            [leaf for leaf in (yield cursor.to_list(length=1000))],
            cls=CustomEncoder))


class LeafHandler(web.RequestHandler):
    @asynchronous
    @gen.engine
    def get(self, _id):
        db = get_default_database(self.application.settings, async=True)
        cursor = db.leaves.find()

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

    @asynchronous
    @gen.engine
    def patch(self, _id):
        data = json.loads(self.request.body)
        if "_id" in data.keys():
            del data["_id"]

        if "type" in data.keys():
            data["type"] = ObjectId(data["type"])

        if "branch" in data.keys():
            data["branch"] = [ObjectId(x) for x in data["branch"]]

        data["modified"] = datetime.now()
        db = get_default_database(self.application.settings, async=True)
        yield db.leaves.update(
            {"_id": ObjectId(_id)},
            {"$set": data}
        )
        result = yield db.leaves.find_one(
            {"_id": ObjectId(_id)},
            {'batteries': False, 'settings': False, 'branch': False}
        )
        self.finish(json.dumps(result, cls=CustomEncoder))


class LeafLogsHandler(web.RequestHandler):
    @asynchronous
    @gen.engine
    def get(self, _id):
        db = get_default_database(self.application.settings, async=True)
        cursor = db.logs.find({
            "log_source": ObjectId(_id)
        }).sort("added", -1)
        self.write("[")

        beginning = True
        current = 0
        while (yield cursor.fetch_next):
            document = cursor.next_object()
            if beginning:
                beginning = False
            else:
                self.write(",")
            self.write(json.dumps(document, cls=CustomEncoder))
            if current > 200:
                break
            else:
                current += 1
        self.finish("]")


class LeafSettingsHandler(web.RequestHandler):
    @asynchronous
    @gen.engine
    def get(self, _id):
        db = get_default_database(self.application.settings, async=True)

        leaf = yield db.leaves.find_one(
            {"_id": ObjectId(_id)},
            {'batteries': False}
        )
        leaf_type = yield db.species.find_one({"_id": leaf["type"]})

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

        result = {
            "custom": leaf.get("settings", {}),
            "common": {
                "address": leaf.get("address"),
                "branch": leaf.get("branch")
            },
            "template": {
                "common": common,
                "custom": leaf_type["settings"]
            }
        }
        self.finish(json.dumps(result, cls=CustomEncoder))

    @asynchronous
    @gen.engine
    def post(self, _id):
        data = json.loads(self.request.body)
        db = get_default_database(self.application.settings, async=True)
        yield db.leaves.update(
            {"_id": ObjectId(_id)},
            {"$set": {
                "settings": data.get("custom", ""),
                "address": data.get("common", {}).get("address", []),
                "branch": [ObjectId(a) for a in data.get("common", {}).get("branch", [])],
                "modified": datetime.now()
            }}
        )

        leaf = yield db.leaves.find_one(
            {"_id": ObjectId(_id)},
            {'batteries': False}
        )
        leaf_type = yield db.species.find_one({"_id": leaf["type"]})

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

        result = {
            "custom": leaf.get("settings", {}),
            "common": {
                "address": leaf.get("address"),
                "branch": leaf.get("branch")
            },
            "template": {
                "common": common,
                "custom": leaf_type["settings"]
            }
        }
        self.finish(json.dumps(result, cls=CustomEncoder))