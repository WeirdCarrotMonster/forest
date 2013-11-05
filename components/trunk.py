# -*- coding: utf-8 -*- 
import subprocess
import os
import tornado.web
import simplejson as json
import urllib
import tornado.httpclient
import pymongo
from components.shadow import encode, decode


class Trunk(tornado.web.Application):
    def __init__(self, settings_dict, **settings):
        super(Trunk, self).__init__(**settings)
        self.settings = settings_dict

    def process_message(self, message):
        function = message.get('function', None)
        if function == "create_leaf":
            response = self.add_leaf(message)
        if function == "status_report":
            response = self.status_report()
        if function == "migrate_leaf":
            response = self.migrate_leaf(message)

        if function is None:
            response = json.dumps({
                "result": "failure",
                "message": "No function or unknown one called"
            })
        return response

    @staticmethod
    def send_message(receiver, contents):
        http_client = tornado.httpclient.HTTPClient()
        post_data = json.dumps(contents)
        post_contents = {
            "message": encode(post_data, receiver["secret"])
        }
        body = urllib.urlencode(post_contents)
        response = json.loads(
            decode(http_client.fetch(
            "http://{0}:{1}".format(receiver["address"], receiver["port"]),
            method='POST',
            body=body
        ).body, receiver["secret"]))
        return response

    def status_report(self):
        result = {
            "success": [],
            "error": [],
        }
        for branch in self.settings["branches"].keys():
            response = self.send_message(
                self.settings["branches"][branch],
                {
                    "function": "status_report"
                }
            )
            if response["result"] == "success":
                if response["role"] == "branch":
                    result["success"].append({
                        "name": branch,
                        "role": "branch"
                    })
                else:
                    result["error"].append({
                        "name": branch,
                        "role": response["role"],
                        "error": "Specified role 'branch' doesn't match response '{0}'".format(response["role"])
                    })
            else:
                result["error"].append({
                    "name": branch,
                    "role": "branch",
                    "error": "Request failed. Is component secret key valid?"
                })

        for root in self.settings["roots"].keys():
            response = self.send_message(
                self.settings["roots"][root],
                {
                    "function": "status_report"
                }
            )
            if response["result"] == "success":
                if response["role"] == "roots":
                    result["success"].append({
                        "name": root,
                        "role": "roots"
                    })
                else:
                    result["error"].append({
                        "name": root,
                        "role": response["role"],
                        "error": "Specified role 'roots' doesn't match response '{0}'".format(response["role"])
                    })
            else:
                result["error"].append({
                    "name": root,
                    "role": "roots",
                    "error": "Request failed. Is component secret key valid?"
                })

        for air in self.settings["air"].keys():
            response = self.send_message(
                self.settings["air"][air],
                {
                    "function": "status_report"
                }
            )
            if response["result"] == "success":
                if response["role"] == "air":
                    result["success"].append({
                        "name": air,
                        "role": "air"
                    })
                else:
                    result["error"].append({
                        "name": air,
                        "role": response["role"],
                        "error": "Specified role 'air' doesn't match response '{0}'".format(response["role"])
                    })
            else:
                result["error"].append({
                    "name": air,
                    "role": "air",
                    "error": "Request failed. Is component secret key valid?"
                })

        return json.dumps(result)

    def call_component_function(self, message):
        # TODO: протестировать
        required_args = ['component', 'name', 'function', 'arguments']
        function_data = {}
        for arg in required_args:
            value = message.get(arg, None)
            if not value:
                return "Argument is missing: {0}".format(arg)
            else:
                function_data[arg] = value

        if not function_data['component'] in ['branch', 'roots', 'air']:
            return json.dumps({
                "result": "failure",
                "message": "unknown component type specified"
            })

        component = None
        try:
            if function_data['component'] == "branch":
                component = self.get_branch(function_data['name'])
            if function_data['component'] == "roots":
                component = self.get_root(function_data['name'])
            if function_data['component'] == "air":
                component = self.get_air(function_data['name'])
        except KeyError:
            return json.dumps({
                "result": "failure",
                "message": "component with specified name not found"
            })

        if not component:
            return json.dumps({
                "result": "failure",
                "message": "failed to get component: logic error, check code"  # реально не должно выпадать
            })

        post_data = {
            "function": function_data['function'],
        }
        arguments = json.loads(function_data['arguments'])

        if type(arguments) != dict:
            return json.dumps({
                "result": "failure",
                "message": "function arguments should be provided in json-encoded dict"
            })

        for arg in arguments.keys():
            post_data[arg] = arguments[arg]

        response = self.send_message(component, post_data)
        return json.dumps({
            "result": response["result"],
            "response": response
        })

    def add_leaf(self, message):
        required_args = ['name', 'address']
        leaf_data = {}
        for arg in required_args:
            value = message.get(arg, None)
            if not value:
                return "Argument is missing: {0}".format(arg)
            else:
                leaf_data[arg] = value

        # =========================================
        # Проверяем, нет ли листа с таким именем в базе
        # =========================================

        client = pymongo.MongoClient(
            self.settings["mongo_host"],
            self.settings["mongo_port"]
        )
        leaves = client.trunk.leaves
        leaf = leaves.find_one({"name": leaf_data["name"]})
        if leaf:
            return "Leaf with name {0} already exists".format(leaf_data["name"])

        # =========================================
        # Обращаемся к roots для создания новой базы
        # =========================================
        root = self.get_root()
        post_data = {
            "function": "prepare_database",
            "name": leaf_data["name"]
        }
        response = self.send_message(root, post_data)
        roots_response = response

        if response["result"] != "success":
            return "Failed to get database settings: {0}".format(response["message"])

        env_for_leaf = json.dumps(response["env"])
        # =========================================
        # Обращаемся к branch для поднятия листа
        # =========================================
        branch = self.get_branch()
        post_data = {
            "function": "create_leaf",
            "name": leaf_data["name"],
            "env": env_for_leaf,
            "initdb": "True"
        }
        response = self.send_message(branch, post_data)
        branch_response = response

        if response["result"] != "success":
            return "Failed to create leaf: {0}".format(response["message"])
        # =========================================
        # Обращаемся к air для публикации листа
        # =========================================
        air = self.get_air()
        post_data = {
            "function": "publish_leaf",
            "name": leaf_data["name"],
            "address": leaf_data["address"],
            "host": response["host"],
            "port": response["port"]
        }
        response = self.send_message(air, post_data)

        leaf = {
            "name": leaf_data["name"],
            "address": leaf_data["address"],
            "branch": "main",
            "port": branch_response["port"],
            "env": roots_response["env"],
        }
        leaves.insert(leaf)

        return "Operation result: {0}".format(json.dumps(response))

    def migrate_leaf(self, message):
        # TODO: доделать
        required_args = ['name', 'source', 'destination']
        leaf_data = {}
        for arg in required_args:
            value = message.get(arg, None)
            if not value:
                return "Argument is missing: {0}".format(arg)
            else:
                leaf_data[arg] = value

        client = pymongo.MongoClient(
            self.settings["mongo_host"],
            self.settings["mongo_port"]
        )
        leaves = client.trunk.leaves
        leaf = leaves.find_one({"name": leaf_data["name"]})
        if not leaf:
            return "Leaf with name {0} not found".format(leaf_data["name"])

        try:
            new_branch = self.get_branch(leaf_data["destination"])
        except:
            return "Destination branch not found"

        try:
            old_branch = self.get_branch(leaf_data["source"])
        except:
            return "Source branch not found"

        # =========================================
        # Обращаемся к новому branch'у для переноса листа
        # =========================================
        post_data = {
            "function": "create_leaf",
            "name": leaf_data["name"],
            "env": json.dumps(leaf["env"]),
            "initdb": "False"
        }
        response = self.send_message(new_branch, post_data)
        new_branch_response = response
        if new_branch_response["result"] != "success":
            return "Failed to create leaf: {0}".format(response["message"])
        # =========================================
        # Обращаемся к air для публикации листа
        # =========================================
        air = self.get_air()
        post_data = {
            "function": "publish_leaf",
            "name": leaf_data["name"],
            "address": leaf["address"],
            "host": new_branch_response["host"],
            "port": new_branch_response["port"]
        }
        response = self.send_message(air, post_data)
        if response["result"] != "success":
            return "Failed to publish leaf: {0}".format(response["message"])
        # =========================================
        # Обращаемся старому branch'у для отключения листа
        # =========================================
        post_data = {
            "function": "delete_leaf",
            "name": leaf_data["name"]
        }
        response = self.send_message(old_branch, post_data)
        old_branch_response = response
        if old_branch_response["result"] != "success":
            return "Failed to create leaf: {0}".format(response["message"])

        leaves.update(
            {"name": leaf_data["name"]},
            {
                "address": leaf["address"],
                "branch": leaf_data["destination"],
                "port": new_branch_response["port"],
                "env": new_branch_response["env"],
            },
            upsert=False,
            multi=False
        )
        return "Moved leaf from {0} to {1}".format(leaf_data["source"], leaf_data["destination"])

    def get_root(self, name="main"):
        return self.settings["roots"][name]

    def get_branch(self, name="main"):
        return self.settings["branches"][name]

    def get_air(self, name="main"):
        return self.settings["air"][name]