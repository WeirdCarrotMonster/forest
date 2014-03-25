# -*- coding: utf-8 -*-
import tornado.web
import simplejson as json
import tornado.httpclient
import tornado.template
from components.shadow import encode, decode
from components.common import check_arguments, get_connection, \
    LogicError, Warning
import hashlib
import traceback


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
            "": "html/index.html",
            "dashboard": "html/dashboard.html",
            "leaves": "html/leaves.html",
            "fauna": "html/fauna.html"
        }

        self.functions = {
            # Обработка состояний сервера
            "update_repository": self.update_repo,
            "check_leaves": self.check_leaves,
            "get_memory_logs": self.get_memory_logs,
            # Работа с ветвями
            "list_branches": self.list_branches,
            # Работа с листьями
            "enable_leaf": self.enable_leaf,
            "disable_leaf": self.disable_leaf,
            "migrate_leaf": self.migrate_leaf,
            "create_leaf": self.add_leaf,
            "rehost_leaf": self.rehost_leaf,
            "change_settings": self.change_settings,
            "get_leaf_logs": self.get_leaf_logs
        }

    def publish_self(self):
        client = get_connection(
            self.settings["mongo_host"],
            self.settings["mongo_port"],
            "admin",
            "password"
        )
        components = client.trunk.components
        instance = components.find_one({"name": self.settings["name"]})

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
            components.insert(about)

        components.update({"name": self.settings["name"]}, about)

    def log_event(self, event, event_type="info"):
        self.logs.append(event)

    def process_page(self, page, user):
        if page in self.safe_urls.keys():
            return self.safe_urls[page]

        if page in self.auth_urls.keys() and user:
            return self.auth_urls[page]

        if page in self.auth_urls.keys() and not user:
            raise Exception("Who's there?")

        raise Exception("I'm sorry, Dave. I'm afraid I can't do that.")

    def process_message(self, message, handler=None, user=None, inner=False):
        self.handler = handler
        self.logs = []
        function = message.get('function', None)

        if function == "login_user":
            return self.login_user(message, user=user)
        if function == "forest_status":
            return self.forest_status(message)

        if not (user or inner):
            raise LogicError("Not authenticated")

        # Далее - функции только для залогиненых
        if not function in self.functions:
            raise LogicError("No function or unknown one called")

        response = self.functions[function](message)
        if len(self.logs) > 0:
            response["logs"] = self.logs
        response["type"] = "result"
        return response

    def send_message(self, receiver, contents):
        print("asdasdas")
        try:
            if receiver["name"] != self.settings["name"]:
                http_client = tornado.httpclient.HTTPClient()
                contents["secret"] = receiver["secret"]
                post_data = json.dumps(contents)
                print("==================")
                print(post_data)
                print("==================")
                body = encode(post_data, receiver["secret"])
                response = json.loads(
                    decode(http_client.fetch(
                        "http://{0}:{1}".format(
                            receiver["host"], receiver["port"]),
                        method='POST',
                        body=body,
                        allow_ipv6=True
                    ).body, receiver["secret"]))
                print(response)
            else:
                response = self.process_message(contents, inner=True)
            return response
        except Exception as e:
            print(traceback.format_exc())
            return {
                "result": "failure",
                "message": e.message
            }

    def get_memory_logs(self, message):
        client = get_connection(
            self.settings["mongo_host"],
            self.settings["mongo_port"],
            "admin",
            "password"
        )
        values = client.trunk.logs.find_one({"type": "memory"}).get("values")
        keys = [leaf["name"] for leaf in client.trunk.leaves.find()]

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

        if self.handler:
            client = get_connection(
                self.settings["mongo_host"],
                self.settings["mongo_port"],
                "admin",
                "password"
            )
            user = client.trunk.users.find_one(
                {
                    "username": user_data["username"],
                    "password": hashlib.md5(user_data["password"]).hexdigest()
                })
            if user:
                self.handler.set_secure_cookie("user", user["username"])
                return {
                    "type": "login",
                    "result": "success",
                    "message": "Successfully logged in",
                    "name": user["username"]
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

    def check_leaves(self, message):
        client = get_connection(
            self.settings["mongo_host"],
            self.settings["mongo_port"],
            "admin",
            "password"
        )

        leaves_list = client.trunk.leaves.find()
        leaves = {}
        for leaf in leaves_list:
            leaves[leaf["name"]] = leaf
            leaves[leaf["name"]]["working"] = False

        success = False
        failure = False

        components = client.trunk.components

        for branch in components.find({"roles.branch": {"$exists": True}}):
            self.log_event({
                "component": "branch",
                "name": branch["name"],
                "message": "Asking branch..."
            })
            response = self.send_message(
                branch,
                {
                    "function": "branch.known_leaves"
                }
            )

            if response["result"] == "success":
                for leaf in response["leaves"]:
                    leaves[leaf["name"]]["working"] = True
                    leaves[leaf["name"]]["host"] = branch["host"]
                    leaves[leaf["name"]]["req"] = leaf.get("req", float(0))
                    leaves[leaf["name"]]["settings"] = leaves[
                        leaf["name"]].get("settings", {})
                    # Лист есть в списке активных и в списке необработанных
                    if leaves[leaf["name"]].get("active", False) and \
                       not leaves[leaf["name"]].get("processed", False):
                        success = success or True
                        leaves[leaf["name"]]["mem"] = leaf["mem"]
                        leaves[leaf["name"]]["processed"] = True
                    # Лист есть в списке активных, но его уже обработали
                    elif leaves[leaf["name"]].get("active", False) and \
                            leaves[leaf["name"]].get("processed", False):
                        self.log_event(
                            {
                                "warning": "Duplicate leaf found",
                                "component": "leaf",
                                "name": leaf["name"],
                                "response": leaf
                            }, event_type="warning")
                    # Листа нет в списке активных, но он активен на ветви
                    else:
                        self.log_event(
                            {
                                "warning": "This leaf shouldn't be active",
                                "component": "leaf",
                                "name": leaf["name"],
                                "response": leaf
                            }, event_type="warning")
            else:
                failure = failure or True
                self.log_event(
                    {
                        "error": "Failed to communicate with branch",
                        "component": "branch",
                        "name": branch["name"],
                        "response": response
                    }, event_type="error")

        if success and not failure:
            return {
                "result": "success",
                "message": "All leaves responded",
                "leaves": leaves
            }
        elif success and failure:
            return {
                "result": "warning",
                "message": "Some leaves failed to respond",
                "leaves": leaves
            }
        else:
            return {
                "result": "failure",
                "message": "No response from leaves",
                "leaves": leaves
            }

    def update_repo(self, message):
        # Проверяем наличие требуемых аргументов
        repo_data = check_arguments(message, ['type'])

        result = {
            "success": [],
            "failure": [],
            "warning": [],
        }

        client = get_connection(
            self.settings["mongo_host"],
            self.settings["mongo_port"],
            "admin",
            "password"
        )

        for branch in client.trunk.branches.find():
            if branch["type"] == repo_data["type"]:
                response = self.send_message(
                    branch,
                    {
                        "function": "branch.update_repository"
                    }
                )
            result[response["result"]].append({
                "branch": branch["name"],
                "response": response
            })
        return result

    def add_leaf(self, message):
        # Проверяем наличие требуемых аргументов
        leaf_data = check_arguments(message, ['name', 'address', 'type'])
        leaf_settings = message.get("settings", {})

        client = get_connection(
            self.settings["mongo_host"],
            self.settings["mongo_port"],
            "admin",
            "password"
        )
        leaves = client.trunk.leaves

        # Проверяем наличие листа с таким именем
        if leaves.find_one({"name": leaf_data["name"]}):
            raise LogicError("Leaf with name '{0}' \
                              already exists".format(leaf_data["name"]))
        # Проверяем наличие листа с таким адресом
        # TODO: переделать логику с учетом групп имен
        if leaves.find_one({"address": leaf_data["address"]}):
            raise LogicError("Leaf with address '{0}' \
                              already exists".format(leaf_data["address"]))

        # Дополнительная проверка на наличие подходящей ветви
        # TODO: анализ нагрузки и более тщательный выбор
        branch = self.get_branch(leaf_data["type"])
        if not branch:
            return {
                "result": "failure",
                "message": "No known branches of type \
                            '{0}'".format(leaf_data["type"])
            }

        leaves.insert({
            "name": leaf_data["name"],
            "active": True,
            "type": leaf_data["type"],
            "address": leaf_data["address"],
            "branch": branch["name"],
            "settings": leaf_settings
        })

        self.update_roots()
        self.update_branches()
        self.update_air()

        response = {
            "result": "success",
            "message": "Successfully added leaf '{0}'".format(leaf_data["name"])
        }
        return response

    def enable_leaf(self, message):
        # Проверяем наличие требуемых аргументов
        leaf_data = check_arguments(message, ['name'])

        client = get_connection(
            self.settings["mongo_host"],
            self.settings["mongo_port"],
            "admin",
            "password"
        )
        leaves = client.trunk.leaves

        # Проверяем, есть ли лист с таким именем в базе
        leaf = leaves.find_one({"name": leaf_data["name"]})
        if not leaf:
            raise LogicError("Leaf with name \
                             '{0}' not found".format(leaf_data["name"]))
        if leaf["active"]:
            raise LogicError(
                "Leaf with name \
                '{0}' already enabled".format(leaf_data["address"])
            )

        # Ищем подходящую ветку для листа
        messages = []
        branch = client.trunk.branches.find_one({"name": leaf["branch"]})
        if not branch:
            branch = self.get_branch(leaf["type"])
            messages.append("Original branch not found; moving to new branch")
        if not branch:
            raise LogicError("No available branches \
                              of type '{0}'".format(leaf["type"]))
        # TODO: при отсутствии ветви необходимого типа,
        # запрашивать создание этого типа на одной из доступных ветвей

        leaves.update(
            {"name": leaf_data["name"]},
            {
                "$set": {
                    "active": True,
                    "branch": branch["name"]
                }
            }
        )

        self.update_branches()
        self.update_air()

        return {
            "result": "success",
            "message": "Re-enabled leaf '{0}'".format(leaf["name"])
        }

    def disable_leaf(self, message):
        # Проверяем наличие требуемых аргументов
        leaf_data = check_arguments(message, ['name'])

        client = get_connection(
            self.settings["mongo_host"],
            self.settings["mongo_port"],
            "admin",
            "password"
        )
        leaves = client.trunk.leaves
        leaf = leaves.find_one({"name": leaf_data["name"]})
        if not leaf:
            raise LogicError("Leaf with name \
                             '{0}' not found".format(leaf_data["name"]))
        if not leaf["active"]:
            raise LogicError("Leaf with name \
                             '{0}' already disabled".format(leaf_data["name"]))

        leaves.update(
            {"name": leaf_data["name"]},
            {
                "$set": {
                    "active": False
                }
            }
        )

        self.update_branches()
        self.update_air()

        return {
            "result": "success",
            "message": "Disabled leaf '{0}'".format(leaf["name"])
        }

    def migrate_leaf(self, message):
        # Проверяем наличие требуемых аргументов
        leaf_data = check_arguments(message, ['name', 'destination'])

        # Ищем лист в базе
        client = get_connection(
            self.settings["mongo_host"],
            self.settings["mongo_port"],
            "admin",
            "password"
        )
        leaves = client.trunk.leaves
        leaf = leaves.find_one({"name": leaf_data["name"]})
        if not leaf:
            raise LogicError("Leaf with name \
                              {0} not found".format(leaf_data["name"]))

        if leaf["branch"] == leaf_data["destination"]:
            raise Warning("Leaf is already on branch \
                           '{0}'".format(leaf["branch"]))

        # Ищем ветви, старую и новую
        components = client.trunk.components
        new_branch = components.find_one({
            "name": leaf_data["destination"],
            "roles.branch.species.{0}".format(leaf["type"]): {"$exists": True}
        })

        if not new_branch:
            raise LogicError("Destination branch not found")

        leaves.update(
            {"name": leaf_data["name"]},
            {
                "$set": {"branch": new_branch["name"]}
            }
        )

        # Обращаемся к новому branch'у для переноса листа
        self.update_branches()
        self.update_air()

        return {
            "result": "success",
            "message": "Moved leaf to {0}".format(leaf_data["destination"])
        }

    def rehost_leaf(self, message):
        # Проверяем наличие требуемых аргументов
        leaf_data = check_arguments(message, ['name', 'address'])

        # Ищем лист в базе
        client = get_connection(
            self.settings["mongo_host"],
            self.settings["mongo_port"],
            "admin",
            "password"
        )
        leaves = client.trunk.leaves
        leaf = leaves.find_one({"name": leaf_data["name"]})
        if not leaf:
            raise LogicError("Leaf with name \
                              {0} not found".format(leaf_data["name"]))

        if leaf["address"] == leaf_data["address"]:
            raise LogicError("Leaf is already on address \
                              '{0}'".format(leaf["address"]))

        client.trunk.leaves.update(
            {"name": leaf_data["name"]},
            {
                "$set": {
                    "address": leaf_data["address"]
                }
            }
        )

        # Обращаемся к air для публикации листа
        self.update_air()

        return {
            "result": "success",
            "message": "Successfully published leaf on \
                        {0}".format(leaf_data["address"])
        }

    def change_settings(self, message):
        # Проверяем наличие требуемых аргументов
        leaf_data = check_arguments(message, ['name', 'settings'])

        if type(leaf_data["settings"]) != dict:
            try:
                leaf_data["settings"] = json.loads(leaf_data["settings"])
            except:
                return {
                    "result": "failure",
                    "message": "Failed to save settings"
                }

        client = get_connection(
            self.settings["mongo_host"],
            self.settings["mongo_port"],
            "admin",
            "password"
        )
        leaves = client.trunk.leaves
        leaf = leaves.find_one({"name": leaf_data["name"]})
        if not leaf:
            raise LogicError("Leaf with name \
                              {0} not found".format(leaf_data["name"]))

        client.trunk.leaves.update(
            {"name": leaf_data["name"]},
            {
                "$set": {
                    "settings": leaf_data["settings"]
                }
            }
        )

        if leaf.get("active", False):
            self.update_branches()

        return {
            "result": "success",
            "message": "Successfully changed settings for leaf \
                        {0}".format(leaf_data["name"])
        }

    def get_leaf_logs(self, message):
        # Проверяем наличие требуемых аргументов
        leaf_data = check_arguments(message, ['name'])

        client = get_connection(
            self.settings["mongo_host"],
            self.settings["mongo_port"],
            "admin",
            "password"
        )
        leaf = client.trunk.leaves.find_one({"name": leaf_data["name"]})
        if not leaf:
            raise LogicError("Leaf with name \
                              {0} not found".format(leaf_data["name"]))

        branch = client.trunk.components.find_one({"name": leaf["branch"]})
        if not branch:
            raise LogicError("Leaf hosted on unknown branch")

        post_data = {
            "function": "branch.get_leaf_logs",
            "name": leaf["name"]
        }
        response = self.send_message(branch, post_data)

        if response["result"] != "success":
            raise LogicError("Failed to get logs from branch")
        return {
            "result": "success",
            "logs": response["logs"]
        }

    def update_air(self):
        client = get_connection(
            self.settings["mongo_host"],
            self.settings["mongo_port"],
            "admin",
            "password"
        )
        components = client.trunk.components
        for component in components.find({"roles.air": {"$exists": True}}):
            self.send_message(component, "air.update_state")

    def update_branches(self):
        client = get_connection(
            self.settings["mongo_host"],
            self.settings["mongo_port"],
            "admin",
            "password"
        )
        components = client.trunk.components
        for branch in components.find({"roles.branch": {"$exists": True}}):
            self.send_message(branch, {"function": "branch.update_state"})

    def update_roots(self):
        client = get_connection(
            self.settings["mongo_host"],
            self.settings["mongo_port"],
            "admin",
            "password"
        )
        components = client.trunk.components
        root = components.find_one({"roles.roots": {"$exists": True}})
        return self.send_message(root, {"function": "roots.update_state"})

    def list_branches(self, message):
        # TODO: переписать с аггрегацией
        client = get_connection(
            self.settings["mongo_host"],
            self.settings["mongo_port"],
            "admin",
            "password"
        )

        branches = []
        components = client.trunk.components
        for branch in components.find({"roles.branch": {"$exists": True}}):
            branches.append({
                "name": branch["name"],
                "type": branch["roles"]["branch"]["species"].keys()
            })

        return {
            "result": "success",
            "branches": branches
        }

    def get_branch(self, species):
        client = get_connection(
            self.settings["mongo_host"],
            self.settings["mongo_port"],
            "admin",
            "password"
        )
        components = client.trunk.components
        return components.find_one({
            "roles.branch": {"$exists": True},
            "roles.branch.species.{0}".format(species): {"$exists": True}
        })

    def cleanup(self):
        if self.branch:
            self.branch.cleanup()
        if self.air:
            self.air.cleanup()
