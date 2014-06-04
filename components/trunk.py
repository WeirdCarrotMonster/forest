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
        self.logs = []

        # Компоненты
        self.branch = None
        self.air = None
        self.roots = None

        self.safe_urls = {
            "login": "html/login.html",
        }
        self.auth_urls = {
            "": "html/dashboard.html"
        }

        self.functions = {
            # Новый лес
            "get_leaves": self.get_leaves,
            "get_leaf_logs": self.get_leaf_logs,
            "toggle_leaf": self.toggle_leaf,
            "get_leaf_settings": self.get_leaf_settings,
            "set_leaf_settings": self.set_leaf_settings,
            "get_default_settings": self.get_default_settings,
            "get_species": self.get_species,
            "create_leaf": self.create_leaf,
            # Обработка состояний сервера
            "update_repository": self.update_repo,
            "get_memory_logs": self.get_memory_logs,
            # Работа с ветвями
            "get_branches": self.get_branches,
            "get_branch_logs": self.get_branch_logs
        }

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

    def log_event(self, event, event_type="info"):
        self.logs.append(event)

    def process_page(self, page, user):
        if page in self.safe_urls.keys():
            return self.safe_urls[page]

        if page in self.auth_urls.keys() and user:
            return self.auth_urls[page]

        if page in self.auth_urls.keys() and not user:
            raise Exception(401)

        raise Exception(404)

    def process_message(self,
                        message,
                        handler=None,
                        user=None,
                        inner=False,
                        callback=None):
        self.handler = handler
        self.logs = []
        function = message.get('function', None)

        if function == "login_user":
            callback(self.login_user(message, user=user))
            return

        if not (user or inner):
            raise LogicError("Not authenticated")

        # Далее - функции только для залогиненых
        if not function in self.functions:
            raise LogicError("No function or unknown one called")

        response = self.functions[function](message)

        if len(self.logs) > 0:
            response["logs"] = self.logs
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
                response = self.process_message(contents, inner=True)
            return response
        except Exception as e:
            return {
                "result": "failure",
                "message": e.message
            }

    def __get_default_settings(self):
        trunk = get_default_database(self.settings)
        branches = trunk.components.find({"roles.branch": {"$exists": True}})

        return {
            "urls": {
                "type": "list",
                "elements": "string",
                "verbose": "Адреса"
            },
            "branch": {
                "type": "checkbox_list",
                "values": [branch["name"] for branch in branches],
                "verbose": "Ветви"
            }
        }

    def get_leaves(self, message):
        trunk = get_default_database(self.settings)

        leaves = trunk.leaves.find().sort('name', pymongo.ASCENDING)
        # TODO: генерировать список средствами MongoDB
        leaves_list = [
            {
                "name": leaf.get("name"),
                "desc": leaf.get("desc"),
                "urls": leaf.get("address") if type(leaf.get("address")) == list else [leaf.get("address")],
                "type": leaf.get("type"),
                "active": leaf.get("active"),
                "branch": leaf.get("branch") if type(leaf.get("branch")) == list else [leaf.get("branch")]
            } for leaf in leaves
        ]
        return { "result": "success", "leaves": leaves_list}

    def get_leaf_logs(self, message):
        # Проверяем наличие требуемых аргументов
        leaf_data = check_arguments(message, ['name'])

        trunk = get_default_database(self.settings)

        log_filter = {
            "log_source": leaf_data["name"]
        }

        logs_raw = trunk.logs.find(log_filter).sort("added", -1).limit(200)
        
        logs = []
        for log in logs_raw:
            logs.insert(0, log)

        return {
            "result": "success",
            "logs": logs
        }

    def toggle_leaf(self, message):
        leaf_data = check_arguments(message, ['name'])

        trunk = get_default_database(self.settings)
        leaves = trunk.leaves

        leaf = leaves.find_one({"name": leaf_data["name"]})

        leaves.update(
            {"name": leaf_data["name"]},
            {
                "$set": {
                    "active": not leaf["active"]
                }
            }
        )

        self.update_branches()
        self.update_air()

        leaf_raw = leaves.find_one({"name": leaf_data["name"]})
        leaf_response = {
            "name": leaf_raw.get("name"),
            "desc": leaf_raw.get("desc"),
            "urls": leaf_raw.get("address") if type(leaf_raw.get("address")) == list else [leaf_raw.get("address")],
            "type": leaf_raw.get("type"),
            "active": leaf_raw.get("active"),
            "branch": leaf_raw.get("branch") if type(leaf_raw.get("branch")) == list else [leaf_raw.get("branch")]
        }

        return {
            "result": "success",
            "leaf": leaf_response
        }

    def get_leaf_settings(self, message):
        leaf_data = check_arguments(message, ['name'])

        trunk = get_default_database(self.settings)
        leaves = trunk.leaves
        species = trunk.species

        leaf = leaves.find_one({"name": leaf_data["name"]})
        leaf_type = species.find_one({"name": leaf["type"]})

        return {
            "result": "success",
            "settings": {
                "custom": leaf.get("settings", {}),
                "common": {
                    "urls": leaf.get("address") if type(leaf.get("address")) == list else [leaf.get("address")],
                    "branch": leaf.get("branch") if type(leaf.get("branch")) == list else [leaf.get("branch")]
                },
                "template": {
                    "common": self.__get_default_settings(),
                    "custom": leaf_type["settings"]
                }
            }
        }

    def set_leaf_settings(self, message):
        leaf_data = check_arguments(message, ['name', 'settings'])

        trunk = get_default_database(self.settings)
        leaves = trunk.leaves

        # TODO: переписать с итерацией по дефолтным настройкам
        leaves.update(
            {"name": leaf_data["name"]},
            {
                "$set": {
                    "settings": leaf_data["settings"]["custom"],
                    "address": leaf_data["settings"]["common"]["urls"],
                    "branch": leaf_data["settings"]["common"]["branch"]
                }
            }
        )

        self.update_branches()

        return {
            "result": "success"
        }        

    def get_default_settings(self, message):
        settings_data = check_arguments(message, ['type'])
        trunk = get_default_database(self.settings)

        leaf_type = trunk.species.find_one({"name": settings_data["type"]})

        return {
            "result": "success",
            "settings": {
                "common": self.__get_default_settings(),
                "custom": leaf_type.get("settings", {})
            }
        }

    def get_species(self, message):
        trunk = get_default_database(self.settings)

        species = []
        for specie in trunk.species.find():
            species.append(specie["name"])

        return {
            "result": "success",
            "species": species
        }

    def create_leaf(self, message):
        leaf_data = check_arguments(message, ['name', 'desc', 'type', 'settings'])

        trunk = get_default_database(self.settings)
        leaves = trunk.leaves

        if leaves.find_one({"name": leaf_data["name"]}):
            raise LogicError("Leaf with name '{0}' \
                              already exists".format(leaf_data["name"]))

        # TODO: проверка адреса

        leaves.insert({
            "name": leaf_data["name"],
            "desc": leaf_data["desc"],
            "type": leaf_data["type"],
            "active": True,
            "address": leaf_data["settings"]["common"]["urls"],
            "branch": leaf_data["settings"]["common"]["branch"],
            "settings": leaf_data["settings"]["custom"]
        })

        self.update_roots()
        self.update_branches()
        self.update_air()

        return {
            "result": "success"
        }

    def get_memory_logs(self, message):
        trunk = get_default_database(self.settings)
        values = trunk.logs.find_one({"type": "memory"}).get("values")
        keys = [leaf["name"] for leaf in trunk.leaves.find()]

        return {
            "type": "result",
            "result": "success",
            "values": values,
            "keys": keys
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

    def update_repo(self, message):
        # Проверяем наличие требуемых аргументов
        repo_data = check_arguments(message, ['type'])
        repo_type = repo_data["type"]
        result = {
            "success": [],
            "failure": [],
            "warning": [],
        }

        trunk = get_default_database(self.settings)

        for branch in trunk.components.find({
                "roles.branch": {"$exists": True},
                "roles.branch.species.%s" % repo_type: {"$exists": True}}):
            response = self.send_message(
                branch,
                {
                    "function": "branch.update_repository",
                    "type": repo_type
                }
            )
            result[response["result"]].append({
                "branch": branch["name"],
                "response": response
            })
        return result

    def update_air(self):
        trunk = get_default_database(self.settings)
        components = trunk.components
        for component in components.find({"roles.air": {"$exists": True}}):
            self.send_message(component, {"function": "air.update_state"})

    def update_branches(self):
        trunk = get_default_database(self.settings)
        components = trunk.components
        for branch in components.find({"roles.branch": {"$exists": True}}):
            self.send_message(branch, {"function": "branch.update_state"})

    def update_roots(self):
        trunk = get_default_database(self.settings)
        components = trunk.components
        root = components.find_one({"roles.roots": {"$exists": True}})
        return self.send_message(root, {"function": "roots.update_state"})

    def get_branches(self, message):
        # TODO: переписать с аггрегацией
        trunk = get_default_database(self.settings)

        branches = []
        components = trunk.components
        for branch in components.find({"roles.branch": {"$exists": True}}):
            branches.append({
                "name": branch["name"],
                "type": branch["roles"]["branch"]["species"].keys()
            })

        return {
            "result": "success",
            "branches": branches
        }

    def get_branch_logs(self, message):
        trunk = get_default_database(self.settings)
        log_filter = {
            "component_type": "branch",
            "component_name": message.get("name")
        }

        logs_raw = trunk.logs.find(log_filter).sort("added", -1).limit(200)
        
        logs = []
        for log in logs_raw:
            logs.insert(0, log)

        return {
            "result": "success",
            "logs": logs
        }

    def cleanup(self):
        if self.branch:
            self.branch.cleanup()
        if self.air:
            self.air.cleanup()
