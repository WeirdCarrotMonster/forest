# -*- coding: utf-8 -*- 

import tornado.web
import simplejson as json
import tornado.httpclient
import pymongo
from components.shadow import encode, decode


class Air(tornado.web.RequestHandler):
    def get(self):
        self.write("Hello to you from trunk!")

    def post(self):
        response = ""
        try:
            message = json.loads(decode(self.get_argument('message', None), self.application.settings["secret"]))
        except:
            self.write(json.dumps({
                "result": "failure",
                "message": "failed to decode message"
            }))
            return
        # Далее message - тело запроса

        function = message.get('function', None)
        if function == "publish_leaf":
            response = self.publish_leaf(message)
        if function == "status_report":
            response = self.status_report()

        self.write(encode(response, self.application.settings["secret"]))

    def status_report(self):
        return json.dumps({
            "result": "success",
            "message": "Working well",
            "role": "air"
        })

    def publish_leaf(self, message):
        required_args = ['name', 'address', 'host', 'port']
        leaf_data = {}
        for arg in required_args:
            value = message.get(arg, None)
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
                upsert=False,
                multi=False
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
        conf = """
$HTTP["host"] == " """ + leaf["address"] + """ " {
    fastcgi.server = ("/" => ((
        "host" => " """ + leaf["host"] + """ ",
        "port" => """ + leaf["port"] + """,
        "check-local" => "disable",
        "disable-time" => 1,
        "fix-root-scriptname" => "enable"
    )))
}
        """
        print(conf)