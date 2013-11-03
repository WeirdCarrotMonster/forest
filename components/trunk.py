# -*- coding: utf-8 -*- 
import subprocess
import os
import tornado.web
import simplejson as json
import urllib
import tornado.httpclient


class Trunk(tornado.web.RequestHandler):
    def get(self):
        self.write("Hello to you from trunk!")

    def post(self):
        function = self.get_argument('function', None)
        response = ""
        if function == "create_leaf":
            response = self.add_leaf()
        self.write(response)

    def add_leaf(self):
        required_args = ['name', 'address']
        leaf_data = {}
        for arg in required_args:
            value = self.get_argument(arg, None)
            if not value:
                return "Argument is missing: {0}".format(arg)
            else:
                leaf_data[arg] = value

        http_client = tornado.httpclient.HTTPClient()

        # =========================================
        # Обращаемся к roots для создания новой базы
        # =========================================
        root = self.get_root()
        post_data = {
            "function": "prepare_database",
            "name": leaf_data["name"]
        }
        body = urllib.urlencode(post_data)
        response = http_client.fetch(
            "http://{0}:{1}".format(root["address"], root["port"]),
            method='POST',
            body=body
        )
        response = json.loads(response.body)
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
            "env": env_for_leaf
        }
        body = urllib.urlencode(post_data)
        response = http_client.fetch(
            "http://{0}:{1}".format(branch["address"], branch["port"]),
            method='POST',
            body=body
        )

        return "Branch created leaf that listens on: {0}".format(response.body)

    def get_root(self):
        return self.application.settings["roots"][0]

    def get_branch(self):
        return self.application.settings["branches"][0]