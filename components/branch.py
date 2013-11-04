# -*- coding: utf-8 -*-

from __future__ import print_function
import os
import tornado.web
from components.leaf import Leaf
import simplejson as json
import pymongo
from components.shadow import encode, decode


def init_leaves(app):
    client = pymongo.MongoClient(
        app.settings["mongo_host"],
        app.settings["mongo_port"]
    )
    leaves = client.branch.leaves
    for leaf in leaves.find():
        print("Found leaf {0} in configuration, starting...".format(leaf["name"]))
        new_leaf = Leaf(
            name=leaf["name"],
            executable=app.settings["executable"],
            fcgi_host=app.settings["host"],
            fcgi_port=leaf["port"],
            pidfile=os.path.join(app.settings["pid_dir"], leaf["name"] + '.pid'),
            env=leaf["env"]
        )
        try:
            app.settings["port_range"].remove(new_leaf.fcgi_port)
        except:
            # Порт не в списке. Стабильности ради делаем НИЧЕГО.
            pass
        new_leaf.start()


class Branch(tornado.web.RequestHandler):
    def get(self):
        self.write("Hello to you from branch!")

    def post(self):
        response = ""
        message = None
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
        if function == "create_leaf":
            response = self.add_leaf(message)

        # TODO: зашифровать ответ
        self.write(response)

    def add_leaf(self, message):
        name = message.get("name", None)
        env = message.get("env", None)
        if not name:
            return json.dumps({
                "result": "failure",
                "message": "missing argument: name"
            })

        if not name:
            return json.dumps({
                "result": "failure",
                "message": "missing argument: env"
            })

        client = pymongo.MongoClient(
            self.application.settings["mongo_host"],
            self.application.settings["mongo_port"]
        )
        leaves = client.branch.leaves
        leaf = leaves.find_one({"name": name})
        if leaf:
            print("Found existing leaf")
            return json.dumps({
                "result": "success",
                "host": self.application.settings["host"],
                "port": leaf["port"],
                "comment": "found existing leaf"
            })

        print("Creating new leaf")

        new_leaf = Leaf(
            name=name,
            executable=self.application.settings["executable"],
            fcgi_host=self.application.settings["host"],
            fcgi_port=self.application.settings["port_range"].pop(),
            pidfile=os.path.join(self.application.settings["pid_dir"], name + '.pid'),
            env=env
        )
        leaf = {
            "name": new_leaf.name,
            "port": new_leaf.fcgi_port,
            "env": new_leaf.launch_env
        }
        leaves.insert(leaf)

        try:
            new_leaf.start()
            self.application.leaves.append(new_leaf)
            new_leaf.prepare_database()
        except:
            self.application.settings["port_range"].append(new_leaf.fcgi_port)
            return json.dumps({
                "result": "failure",
                "message": ""
            })
        else:
            return json.dumps({
                "result": "success",
                "host": self.application.settings["host"],
                "port": new_leaf.fcgi_port,
                "comment": "created new leaf"
            })

    def del_leaf(self):
        name = self.get_argument("name", None)
        if not name:
            return json.dumps({
                "result": "failure",
                "message": "missing argument: name"
            })

        for leaf in self.application.leaves:
            if leaf.name == name:
                leaf.stop()
                self.application.leaves.remove(leaf)
                break

        client = pymongo.MongoClient(
            self.application.settings["mongo_host"],
            self.application.settings["mongo_port"]
        )
        leaves = client.branch.leaves
        leaves.remove({"name": name})

        return json.dumps({
            "result": "success",
            "message": "deleted leaf info from server"
        })