# -*- coding: utf-8 -*-
import tornado.web
import simplejson as json
import tornado.httpclient
import tornado.template
import pymongo
from components.common import check_arguments, get_default_database, \
    LogicError, authenticate_user


class Trunk(tornado.web.Application):
    def __init__(self, settings_dict, **settings):
        super(Trunk, self).__init__(**settings)
        self.settings = settings_dict
        self.settings["cookie_secret"] = "asdasd"
        self.handler = None

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

        self.functions = {} # Заполняется функциями при подключении модулей

    def publish_self(self):
        trunk = get_default_database(self.settings)
        instance = trunk.components.find_one({"name": self.settings["name"]})

        about = {
            "name": self.settings["name"],
            "host": self.settings["host"],
            "port": self.settings["port"],
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

        if page in self.auth_urls.keys() and user:
            return self.auth_urls[page]

        if page in self.auth_urls.keys() and not user:
            raise Exception(401)

        raise Exception(404)

    def unknown_function_handler(self, **kwargs):
        return {}

    def process_message(self,
                        message,
                        handler=None,
                        user=None,
                        inner=False):
        self.handler = handler
        function = message.get('function', None)

        if function == "login_user":
            return self.login_user(message, user=user)

        if not (user or inner):
            raise LogicError("Not authenticated")

        # Далее - функции только для залогиненых
        if not function in self.functions:
            raise LogicError("No function or unknown one called")

        response = self.functions.get(function, self.unknown_function_handler)(**message)
        response["type"] = "result"

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
                response = self.process_message(contents, inner=True)
            return response
        except Exception as e:
            return {
                "result": "failure",
                "message": e.message
            }

    def login_user(self, message, user=None):
        if user:
            return {
                "type": "login",
                "result": "success",
                "message": "Already authenticated"
            }

        user_data = check_arguments(message, ['username', 'password'])
        username = user_data["username"]
        password = user_data["password"]

        if self.handler:
            if authenticate_user(self.settings, username, password):
                self.handler.set_secure_cookie("user", username)
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
        return {
            "type": "result",
            "result": "error",
            "message": "Failed to authenticate"
        }

    def cleanup(self):
        if self.branch:
            self.branch.cleanup()
        if self.air:
            self.air.cleanup()
