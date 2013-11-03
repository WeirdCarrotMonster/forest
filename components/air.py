# -*- coding: utf-8 -*- 

import tornado.web
import simplejson as json
import tornado.httpclient
import pymongo


class Air(tornado.web.RequestHandler):
    def get(self):
        self.write("Hello to you from trunk!")

    def post(self):
        function = self.get_argument('function', None)
        response = ""
        if function == "publish_leaf":
            response = self.publish_leaf()
        self.write(response)

    def publish_leaf(self):
        required_args = ['name', 'address', 'host', 'port']
        leaf_data = {}
        for arg in required_args:
            value = self.get_argument(arg, None)
            if not value:
                return json.dumps({
                    "result": "failure",
                    "message": "missing argument: {0}".format(arg)
                })
            else:
                leaf_data[arg] = value

        print("Publishing leaf {0} on address {1}".format(leaf_data["name"], leaf_data["address"]))

        client = pymongo.MongoClient(
            self.application.settings["mongo_host"],
            self.application.settings["mongo_port"]
        )
        leaves = client.air.leaves
        leaf = leaves.find_one({"name": leaf_data["name"]})

        if leaf:
            leaves.update(
                {"name": leaf_data["name"]},
                {
                    "address": leaf_data["address"],
                    "host": leaf_data["host"],
                    "port": leaf_data["port"]
                },
                {}
            )
        else:
            leaves.insert({
                "name": leaf_data["name"],
                "address": leaf_data["address"],
                "host": leaf_data["host"],
                "port": leaf_data["port"]
            })
        return json.dumps({
            "result": "success",
            "message": "Published leaf {0} on address {1}".format(leaf_data["name"], leaf_data["address"])
        })


def get_leaves_proxy(settings):
    client = pymongo.MongoClient(
        settings["settings"]["mongo_host"],
        settings["settings"]["mongo_port"]
    )
    leaves = client.air.leaves
    for leaf in leaves.find():
        print(leaf)
    # TODO: подходящее форматирование