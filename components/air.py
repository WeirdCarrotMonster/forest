# -*- coding: utf-8 -*-
import subprocess
import tornado.web
import tornado.httpclient
import pymongo


class Air(tornado.web.Application):

    def __init__(self, settings_dict, **settings):
        super(Air, self).__init__(**settings)
        self.settings = settings_dict

        self.functions = {
            "publish_leaf": self.publish_leaf,
            "unpublish_leaf": self.unpublish_leaf,
            "status_report": self.status_report
        }

    def process_message(self, message):
        function = message.get('function', None)

        if not function in self.functions:
            return {
                "result": "failure",
                "message": "No function or unknown one called"
            }

        return self.functions[function](message)

    def status_report(self, message):
        return {
            "result": "success",
            "message": "Working well",
            "role": "air"
        }

    def publish_leaf(self, message):
        required_args = ['name', 'address', 'host', 'port']
        leaf_data = {}
        for arg in required_args:
            value = message.get(arg, None)
            if not value:
                return {
                    "result": "failure",
                    "message": "missing argument: {0}".format(arg)
                }
            else:
                leaf_data[arg] = value

        print("Publishing leaf {0} on address {1}".format(
            leaf_data["name"],
            leaf_data["address"])
        )

        client = pymongo.MongoClient(
            self.settings["mongo_host"],
            self.settings["mongo_port"]
        )
        leaves = client.air.leaves
        leaf = leaves.find_one({"name": leaf_data["name"]})

        if leaf:
            leaves.update(
                {"name": leaf_data["name"]},
                {
                    "name": leaf_data["name"],
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

        self.reload_proxy()
        return {
            "result": "success",
            "message": "Published leaf {0} on address {1}".format(
                leaf_data["name"],
                leaf_data["address"]
            )
        }

    def unpublish_leaf(self, message):
        required_args = ['name']
        leaf_data = {}
        for arg in required_args:
            value = message.get(arg, None)
            if not value:
                return {
                    "result": "failure",
                    "message": "missing argument: {0}".format(arg)
                }
            else:
                leaf_data[arg] = value

        client = pymongo.MongoClient(
            self.settings["mongo_host"],
            self.settings["mongo_port"]
        )
        leaves = client.air.leaves
        leaves.remove({"name": leaf_data["name"]})
        self.reload_proxy()
        return {
            "result": "success",
            "message": "Removed leaf '{0}' from air server".format(
                leaf_data["name"])
        }

    def reload_proxy(self):
        cmd = self.settings["proxy_restart_command"].split()
        subprocess.Popen(cmd, shell=False)


def get_leaves_proxy(settings):
    client = pymongo.MongoClient(
        settings["settings"]["mongo_host"],
        settings["settings"]["mongo_port"]
    )
    leaves = client.air.leaves
    for leaf in leaves.find():
        host = leaf["address"]
        if ":" in host:
            host = "[" + host + "]"
        conf = '''
$HTTP["host"] == "''' + host + '''" {
    fastcgi.server = ("/" => ((
        "host" => "''' + leaf["host"] + '''",
        "port" => ''' + str(leaf["port"]) + ''',
        "check-local" => "disable",
        "disable-time" => 1,
        "fix-root-scriptname" => "enable"
    )))
}
        '''
        print(conf)
