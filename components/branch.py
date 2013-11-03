# -*- coding: utf-8 -*-

import os
import tornado.web
from leaf import *


class Branch(tornado.web.RequestHandler):
    def get(self):
        self.write("Hello to you from branch!")

    def post(self):
        self.write("Hello to you from branch!")

    def add_leaf(self, name):

        new_leaf = Leaf(
            name=name,
            executable=self.application.settings["executable"],
            fcgi_host=self.application.settings["host"],
            fcgi_port=self.application.settings["port_range"].pop(),
            pidfile=os.path.join(self.application.settings["pid_dir"], name + '.pid')
        )
        try:
            new_leaf.start()
            self.application.leaves.append(new_leaf)
        except:
            self.application.settings["port_range"].append(new_leaf.fcgi_port)
            # TODO: Ну и эксешпон дальше прокинуть не помешает

    def delete_leaves(self, leaf_names):
        if not type(leaf_names) == list:
            leaves = [leaf_names]
