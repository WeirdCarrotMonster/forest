# -*- coding: utf-8 -*-
from __future__ import print_function
import os
import tornado.web
from subprocess import CalledProcessError, check_output, STDOUT
from components.leaf import Leaf
from components.common import log_message, ArgumentMissing, check_arguments
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

        self.functions = {
            "create_leaf": self.add_leaf,
            "delete_leaf": self.delete_leaf,
            "restart_leaf": self.restart_leaf,
            "change_settings": self.change_settings,
            "get_leaf_logs": self.get_leaf_logs,
            "status_report": self.status_report,
            "known_leaves": self.known_leaves,
            "update_repository": self.update_repo
        }

    def process_message(self, message):
        function = message.get('function', None)

        if not function in self.functions:
            return {
                "result": "failure",
                "message": "No function or unknown one called"
            }

        return self.functions[function](message)

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
                chdir=self.settings["chdir"],
                executable=self.settings["executable"],
                fcgi_host=self.settings["host"],
                fcgi_port=leaf["port"],
                pidfile=os.path.join(self.settings["pid_dir"],
                                     leaf["name"] + '.pid'),
                logfile=os.path.join(self.settings["log_dir"],
                                     leaf["name"] + '.log'),
                env=leaf.get("env", {}),
                settings=leaf.get("settings", {})
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

    def status_report(self, message):
        return {
            "result": "success",
            "message": "Working well",
            "role": "branch"
        }

    def known_leaves(self, message):
        known_leaves = []
        for leaf in self.leaves:
            known_leaves.append({
                "name": leaf.name,
                "port": leaf.fcgi_port,
                "env": leaf.launch_env,
                "settings": leaf.settings,
                "mem": leaf.mem_usage(),
                "req": leaf.req_per_second()
            })
        return {
            "result": "success",
            "leaves": known_leaves
        }

    def add_leaf(self, message):
        leaf_data = check_arguments(message, ["name", "env"], [("settings", {}), ("initdb", True)])
        if type(leaf_data["env"]) != dict:
            return {
                "result": "failure",
                "message": "Environment should be dict"
            }

        if type(leaf_data["settings"]) != dict:
            return {
                "result": "failure",
                "message": "Settings should be dict"
            }

        client = pymongo.MongoClient(
            self.settings["mongo_host"],
            self.settings["mongo_port"]
        )
        leaves = client.branch.leaves
        leaf = leaves.find_one({"name": leaf_data["name"]})
        if leaf:
            log_message(
                "Found existing leaf: {0}".format(leaf_data["name"]), component="Branch")
            return {
                "result": "success",
                "host": self.settings["host"],
                "port": leaf["port"],
                "comment": "found existing leaf"
            }

        log_message("Creating new leaf: {0}, with initdb: {1}".format(
            leaf_data["name"], leaf_data["initdb"]), component="Branch")

        new_leaf = Leaf(
            name=leaf_data["name"],
            chdir=self.settings["chdir"],
            executable=self.settings["executable"],
            fcgi_host=self.settings["host"],
            fcgi_port=self.settings["port_range"].pop(),
            pidfile=os.path.join(self.settings["pid_dir"], leaf_data["name"] + '.pid'),
            logfile=os.path.join(self.settings["log_dir"], leaf_data["name"] + '.log'),
            env=leaf_data["env"],
            settings=leaf_data["settings"]
        )

        try:
            new_leaf.start()
            self.leaves.append(new_leaf)
            if leaf_data["initdb"]:
                new_leaf.init_database()
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
                "env": leaf_data["env"],
                "settings": leaf_data["settings"]
            }
            leaves.insert(leaf)

            return {
                "result": "success",
                "host": self.settings["host"],
                "port": new_leaf.fcgi_port,
                "comment": "created new leaf"
            }

    def delete_leaf(self, message):
        leaf_data = check_arguments(message, ["name"])

        for leaf in self.leaves:
            if leaf.name == leaf_data["name"]:
                leaf.stop()
                self.leaves.remove(leaf)

        log_message("Deleting leaf '{0}' from server".format(leaf_data["name"]),
                    component="Branch")

        client = pymongo.MongoClient(
            self.settings["mongo_host"],
            self.settings["mongo_port"]
        )
        leaves = client.branch.leaves
        leaves.remove({"name": leaf_data["name"]})

        return {
            "result": "success",
            "message": "deleted leaf info from server"
        }

    def restart_leaf(self, message):
        leaf_data = check_arguments(message, ["name"])

        for leaf in self.leaves:
            if leaf.name == leaf_data["name"]:
                leaf.stop()
                leaf.start()

        log_message("Restarting leaf '{0}'".format(leaf_data["name"]), component="Branch")

        return {
            "result": "success",
            "message": "restarted leaf {0}".format(leaf_data["name"])
        }

    def change_settings(self, message):
        leaf_data = check_arguments(message, ["name", "settings"])

        if type(leaf_data["settings"]) != dict:
            return {
                "result": "failure",
                "message": "Settings should be dict"
            }
        client = pymongo.MongoClient(
            self.settings["mongo_host"],
            self.settings["mongo_port"]
        )
        leaf = client.branch.leaves.find_one({"name": leaf_data["name"]})
        if not leaf:
            return {
                "result": "failure",
                "message": "Leaf with name {0} not found".format(leaf_data["name"])
            }

        client.branch.leaves.update(
            {"name": leaf_data["name"]},
            {
                "$set": {
                    "settings": leaf_data["settings"]
                }
            },
            upsert=False,
            multi=False
        )

        for leaf in self.leaves:
            if leaf.name == leaf_data["name"]:
                leaf.stop()
                leaf.set_settings(leaf_data["settings"])
                leaf.start()

        return {
            "result": "success",
            "message": "Saved settings for leaf {0}".format(leaf_data["name"])
        }

    def get_leaf_logs(self, message):
        leaf_data = check_arguments(message, ["name"])

        logs = None
        for leaf in self.leaves:
            if leaf.name == leaf_data["name"]:
                logs = leaf.get_logs()
        if logs is None:
            return {
                "result": "failure",
                "message": "Leaf with name {0} not found".format(leaf_data["name"])
            }

        return {
            "result": "success",
            "logs": logs
        }

    def update_repo(self, message):
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
            leaf.update_database()
            leaf.start()
        return result
