# -*- coding: utf-8 -*-

from __future__ import print_function
import os
import tornado.web
from components.leaf import Leaf
import simplejson as json


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

        env = self.get_argument("env", "")
        new_leaf = Leaf(
            name=name,
            executable=self.application.settings["executable"],
            fcgi_host=self.application.settings["host"],
            fcgi_port=self.application.settings["port_range"].pop(),
            pidfile=os.path.join(self.application.settings["pid_dir"], name + '.pid'),
            env=env
        )
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
                "port": new_leaf.fcgi_port
            })
