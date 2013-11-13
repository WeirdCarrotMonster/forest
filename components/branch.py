# -*- coding: utf-8 -*-
from __future__ import print_function
import os
import tornado.web
from subprocess import CalledProcessError, check_output, STDOUT
from components.leaf import Leaf
from components.common import log_message
import pymongo
import traceback


class Branch(tornado.web.Application):
    def __init__(self, settings_dict, **settings):
        super(Branch, self).__init__(**settings)
        self.settings = settings_dict
        self.leaves = []
        self.settings["port_range"] = range(
            self.settings["port_range_begin"], 
            self.settings["port_range_end"])
        self.init_leaves()

    def process_message(self, message):
        response = None
        function = message.get('function', None)
        if function == "create_leaf":
            response = self.add_leaf(message)
        if function == "delete_leaf":
            response = self.delete_leaf(message)
        if function == "status_report":
            response = self.status_report()
        if function == "known_leaves":
            response = self.known_leaves()
        if function == "update_repository":
            response = self.update_repo()

        if function is None:
            response = {
                "result": "failure",
                "message": "No function or unknown one called"
            }

        if response:
            return response
        else:
            return {
                "result": "failure",
                "message": "Unknown error occured"
            }

    def init_leaves(self):
        client = pymongo.MongoClient(
            self.settings["mongo_host"],
            self.settings["mongo_port"]
        )
        leaves = client.branch.leaves
        for leaf in leaves.find():
            log_message("Found leaf {0} in configuration".format(
                leaf["name"]), 
                component="Branch"
                )
            new_leaf = Leaf(
                name=leaf["name"],
                executable=self.settings["executable"],
                fcgi_host=self.settings["host"],
                fcgi_port=leaf["port"],
                pidfile=os.path.join(self.settings["pid_dir"], 
                    leaf["name"] + '.pid'),
                env=leaf.get("env", ""),
                settings=leaf.get("settings", "")
            )
            try:
                self.settings["port_range"].remove(new_leaf.fcgi_port)
            except ValueError:
                # Порт не в списке. Стабильности ради делаем НИЧЕГО.
                pass
            new_leaf.start()
            self.leaves.append(new_leaf)

    def shutdown_leaves(self):
        log_message("Shutting down leaves...", component="Branch")
        for leaf in self.leaves:
            leaf.stop()

    def status_report(self):
        return {
            "result": "success",
            "message": "Working well",
            "role": "branch"
        }

    def known_leaves(self):
        known_leaves = []
        for leaf in self.leaves:
            known_leaves.append({
                "name": leaf.name,
                "port": leaf.fcgi_port ,
                "env": leaf.launch_env,
                "settings": leaf.settings,
                "mem": leaf.mem_usage()
            })
        result = {
            "result": "success",
            "leaves": known_leaves
        }
        return result

    def add_leaf(self, message):
        name = message.get("name", None)
        env = message.get("env", None)
        settings = message.get("env", None)
        initdb = bool(message.get("initdb", False))
        if not name:
            return {
                "result": "failure",
                "message": "missing argument: name"
            }

        if not name:
            return {
                "result": "failure",
                "message": "missing argument: env"
            }

        client = pymongo.MongoClient(
            self.settings["mongo_host"],
            self.settings["mongo_port"]
        )
        leaves = client.branch.leaves
        leaf = leaves.find_one({"name": name})
        if leaf:
            log_message("Found existing leaf: {0}".format(name), 
                component="Branch")
            return {
                "result": "success",
                "host": self.settings["host"],
                "port": leaf["port"],
                "comment": "found existing leaf"
            }

        log_message("Creating new leaf: {0}".format(name), component="Branch")

        new_leaf = Leaf(
            name=name,
            executable=self.settings["executable"],
            fcgi_host=self.settings["host"],
            fcgi_port=self.settings["port_range"].pop(),
            pidfile=os.path.join(self.settings["pid_dir"], name + '.pid'),
            env=env,
            settings=settings
        )

        try:
            new_leaf.start()
            self.leaves.append(new_leaf)
            if initdb:
                new_leaf.prepare_database()
        except Exception:
            self.settings["port_range"].append(new_leaf.fcgi_port)
            return {
                "result": "failure",
                "message": "Start failed: {0}".format(traceback.format_exc())
            }
        else:
            leaf = {
                "name": new_leaf.name,
                "port": new_leaf.fcgi_port,
                "env": new_leaf.launch_env,
                "settings": new_leaf.settings
            }
            leaves.insert(leaf)

            return {
                "result": "success",
                "host": self.settings["host"],
                "port": new_leaf.fcgi_port,
                "comment": "created new leaf"
            }

    def delete_leaf(self, message):
        name = message.get("name", None)
        if not name:
            return {
                "result": "failure",
                "message": "missing argument: name"
            }

        for leaf in self.leaves:
            if leaf.name == name:
                leaf.stop()
                self.leaves.remove(leaf)

        log_message("Deleting leaf '{0}' from server".format(name), 
            component="Branch")

        client = pymongo.MongoClient(
            self.settings["mongo_host"],
            self.settings["mongo_port"]
        )
        leaves = client.branch.leaves
        leaves.remove({"name": name})

        return {
            "result": "success",
            "message": "deleted leaf info from server"
        }

    def update_repo(self):
        try:
            path = self.settings["repository"]["path"]
            repo_type = self.settings["repository"]["type"]
        except KeyError:
            return {
                "result": "warning",
                "message": "No repository present"
            }

        try:
            if repo_type == "git":
                cmd = [
                    "git", 
                    "--git-dir={0}/.git".format(path), 
                    "--work-tree={0}".format(path), 
                    "pull"
                ]
                output = check_output(cmd, stderr=STDOUT)
                result = {
                    "result": "success",
                    "message": output
                }
            else:
                result = {
                    "result": "failure",
                    "message": "configuration error: unknown repository type"
                }
        except CalledProcessError:
            result = {
                "result": "failure",
                "message": traceback.format_exc()
            }
        for leaf in self.leaves:
            leaf.stop()
            leaf.start()
        return result
