# -*- coding: utf-8 -*-

from __future__ import print_function
import os
import tornado.web
from components.leaf import Leaf
import simplejson as json
import pymongo


def init_leaves(app):
    client = pymongo.MongoClient(
        app.settings["mongo_host"],
        app.settings["mongo_port"]
    )
    leaves = client.branch.leaves
    for leaf in leaves.find():  # TODO: устанавливать флаг активный-неактивный и фильтровать по нему
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
        function = self.get_argument('function', None)
        response = ""
        if function == "create_leaf":
            response = self.add_leaf()
        self.write(response)

    def add_leaf(self):
        name = self.get_argument("name", None)
        if not name:
            return "Argument is missing: name"

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
        env = self.get_argument("env", "")
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
