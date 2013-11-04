# -*- coding: utf-8 -*- 
import subprocess
import os
import tornado.web
import simplejson as json
import urllib
import tornado.httpclient
from components.shadow import encode, decode


class Trunk(tornado.web.RequestHandler):
    def get(self):
        self.write("Hello to you from trunk!")

    def post(self):
        function = self.get_argument('function', None)
        response = ""
        if function == "create_leaf":
            response = self.add_leaf()
        self.write(response)

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
        response = self.send_message(root, post_data)

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

        response = self.send_message(branch, post_data)

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

        return "Operation result: {0}".format(json.dumps(response))

    def get_root(self):
        return self.application.settings["roots"][0]

    def get_branch(self):
        return self.application.settings["branches"][0]

    def get_air(self):
        return self.application.settings["air"][0]