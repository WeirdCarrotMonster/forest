# -*- coding: utf-8 -*-
import traceback

import simplejson as json
import tornado.httpclient
import tornado.template
import tornado.web

from components.common import LogicError
from components.database import authenticate_user, get_default_database


class Trunk(tornado.web.Application):
    def __init__(self, settings_dict, **settings):
        super(Trunk, self).__init__(**settings)
        self.settings = settings_dict
        self.settings["cookie_secret"] = "asdasd"

        # Компоненты
        self.branch = None
        self.air = None
        self.roots = None
        self.druid = None

        self.safe_urls = {
            "login": "html/login.html",
        }
        self.auth_urls = {
            "": "html/dashboard.html"
        }

        self.functions = {}  # Заполняется функциями при подключении модулей
        self.initial_publish()

    def initial_publish(self):
        trunk = get_default_database(self.settings)
        instance = trunk.components.find_one({"name": self.settings["name"]})

        if not instance:
            about = {
                "name": self.settings["name"],
                "host": self.settings["trunk_host"],
                "port": self.settings["trunk_port"],
                "secret": self.settings["secret"],
                "roles": {}
            }
            instance = trunk.components.insert(about)
        self.settings["id"] = instance.get("_id")

    def publish_self(self):
        trunk = get_default_database(self.settings)
        instance = trunk.components.find_one({"name": self.settings["name"]})

        about = {
            "name": self.settings["name"],
            "host": self.settings["trunk_host"],
            "port": self.settings["trunk_port"],
            "secret": self.settings["secret"],
            "roles": {}
        }
        if self.branch:
            about["roles"]["branch"] = self.branch.settings
        if self.air:
            about["roles"]["air"] = self.air.settings
        if self.roots:
            about["roles"]["roots"] = self.roots.settings

        if not instance:
            trunk.components.insert(about)

        trunk.components.update({"name": self.settings["name"]}, about)

    def process_page(self, page, user):
        if page in self.safe_urls.keys():
            return self.safe_urls[page]

        if not user:
            raise Exception(401)

        return self.auth_urls[""]

    def unknown_function_handler(self, **kwargs):
        return {}

    def process_message(self,
                        message,
                        handler,
                        user=None,
                        inner=False,
                        callback=None):
        function = message.get('function', None)

        if function == "login_user":
            callback(self.login_user(user=user, handler=handler, **message))
            return

        if not (user or inner):
            raise LogicError("Not authenticated")

        # Далее - функции только для залогиненых
        if not function in self.functions:
            raise LogicError("No function or unknown one called")

        response = self.functions.get(function, self.unknown_function_handler)(**message)
        response["type"] = "result"

        if callback:
            callback(response)
        else:
            return response

    def send_message(self, receiver, contents):
        try:
            if receiver["name"] != self.settings["name"]:
                http_client = tornado.httpclient.HTTPClient()
                contents["secret"] = receiver["secret"]
                post_data = json.dumps(contents)
                body = post_data
                response = json.loads(
                    http_client.fetch(
                        "http://{0}:{1}".format(
                            receiver["host"], receiver["port"]),
                        method='POST',
                        body=body,
                        allow_ipv6=True
                    ).body)
            else:
                response = self.process_message(contents, None, inner=True)
            return response
        except Exception as e:
            print(traceback.format_exc())
            return {
                "result": "failure",
                "message": e.message
            }

    def login_user(self, username, password, handler, user=None, **kwargs):
        if user:
            return {
                "type": "login",
                "result": "success",
                "message": "Already authenticated"
            }

        if authenticate_user(self.settings, username, password):
            handler.set_secure_cookie("user", username)
            return {
                "type": "login",
                "result": "success",
                "message": "Successfully logged in",
                "name": username
            }
        else:
            return {
                "type": "login",
                "result": "error",
                "message": "Wrong credentials"
            }

    def cleanup(self):
        if self.branch:
            self.branch.cleanup()
        if self.air:
            self.air.cleanup()
