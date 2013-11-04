# -*- coding: utf-8 -*-

from __future__ import print_function
import os
import tornado.web
from components.leaf import Leaf
import simplejson as json
import pymongo



class Branch(tornado.web.Application):
    def __init__(self, settings_dict, **settings):
        super(Branch, self).__init__(**settings)
        self.settings = settings_dict
        self.leaves = []
        self.settings["port_range"] = range(self.settings["port_range_begin"], self.settings["port_range_end"])
        self.init_leaves()

    def process_message(self, message):
        function = message.get('function', None)
        if function == "create_leaf":
            response = self.add_leaf(message)
        if function == "status_report":
            response = self.status_report()
        if function == "known_leaves":
            response = self.known_leaves()

        if function is None:
            response = json.dumps({
                "result": "failure",
                "message": "No function or unknown one called"
            })
        return response

    def init_leaves(self):
        client = pymongo.MongoClient(
            self.settings["mongo_host"],
            self.settings["mongo_port"]
        )
        leaves = client.branch.leaves
        for leaf in leaves.find():
            print("Found leaf {0} in configuration, starting...".format(leaf["name"]))
            new_leaf = Leaf(
                name=leaf["name"],
                executable=self.settings["executable"],
                fcgi_host=self.settings["host"],
                fcgi_port=leaf["port"],
                pidfile=os.path.join(self.settings["pid_dir"], leaf["name"] + '.pid'),
                env=leaf["env"]
            )
            try:
                self.settings["port_range"].remove(new_leaf.fcgi_port)
            except:
                # Порт не в списке. Стабильности ради делаем НИЧЕГО.
                pass
            new_leaf.start()
            self.leaves.append(new_leaf)

    def shutdown_leaves(self):
        print("Shutting down leaves...")
        for leaf in self.leaves:
            leaf.stop()

    def status_report(self):
        return json.dumps({
            "result": "success",
            "message": "Working well",
            "role": "branch"
        })

    def known_leaves(self):
        client = pymongo.MongoClient(
            self.settings["mongo_host"],
            self.settings["mongo_port"]
        )
        leaves = client.branch.leaves
        known_leaves = []
        for leaf in leaves.find():
            known_leaves.append({
                "name": leaf["name"],
                "port": leaf["port"],
                "env": leaf["env"],
            })
        result = {
            "result": "success",
            "leaves": known_leaves
        }
        return json.dumps(result)

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
            self.settings["mongo_host"],
            self.settings["mongo_port"]
        )
        leaves = client.branch.leaves
        leaf = leaves.find_one({"name": name})
        if leaf:
            print("Found existing leaf")
            return json.dumps({
                "result": "success",
                "host": self.settings["host"],
                "port": leaf["port"],
                "comment": "found existing leaf"
            })

        print("Creating new leaf")

        new_leaf = Leaf(
            name=name,
            executable=self.settings["executable"],
            fcgi_host=self.settings["host"],
            fcgi_port=self.settings["port_range"].pop(),
            pidfile=os.path.join(self.settings["pid_dir"], name + '.pid'),
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
            self.leaves.append(new_leaf)
            new_leaf.prepare_database()
        except:
            self.settings["port_range"].append(new_leaf.fcgi_port)
            return json.dumps({
                "result": "failure",
                "message": ""
            })
        else:
            return json.dumps({
                "result": "success",
                "host": self.settings["host"],
                "port": new_leaf.fcgi_port,
                "comment": "created new leaf"
            })

    def del_leaf(self, message):
        name = message.get("name", None)
        if not name:
            return json.dumps({
                "result": "failure",
                "message": "missing argument: name"
            })

        for leaf in self.leaves:
            if leaf.name == name:
                leaf.stop()
                self.leaves.remove(leaf)

        client = pymongo.MongoClient(
            self.settings["mongo_host"],
            self.settings["mongo_port"]
        )
        leaves = client.branch.leaves
        leaves.remove({"name": name})

        return json.dumps({
            "result": "success",
            "message": "deleted leaf info from server"
        })