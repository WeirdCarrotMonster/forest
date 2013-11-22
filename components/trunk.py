# -*- coding: utf-8 -*- 
import tornado.web
import simplejson as json
import tornado.httpclient
import tornado.template
import pymongo
from components.shadow import encode, decode
import hashlib


class Trunk(tornado.web.Application):
    def __init__(self, settings_dict, **settings):
        super(Trunk, self).__init__(**settings)
        self.settings = settings_dict
        self.settings["cookie_secret"] = 'asdfasdf'
        self.socket = None
        self.handler = None
        self.logs = []

    def log_event(self, event, type="info"):
        if self.socket:
            event["type"] = type
            self.socket.send_message(event)
        else:
            self.logs.append(event)

    def process_message(self, message, socket=None, handler=None, user=None):
        self.socket = socket
        self.handler = handler
        response = None
        function = message.get('function', None)
        if function is None:
            response = {
                "result": "failure",
                "message": "No function or unknown one called"
            }

        if function == "known_functions":
            response = self.known_functions(message)
        if function == "login_user":
            response = self.login_user(message, user=user)

        # Далее - функции только для залогиненых
        if not response and not user:
            return {
                "result": "failure",
                "type": "result",
                "message": "Not authenticated"
            }

        # Обработка состояний сервера
        if function == "status_report":
            response = self.status_report(message)
        if function == "update_repository":
            response = self.update_repo(message)
        if function == "check_leaves":
            response = self.check_leaves(message)

        # Работа с ветвями
        if function == "add_branch":
            response = self.add_branch(message)
        if function == "get_branches":
            response = self.get_branches(message)
        if function == "modify_branch":
            response = self.modify_branch(message)

        # Работа с листьями
        if function == "enable_leaf":
            response = self.enable_leaf(message)
        if function == "disable_leaf":
            response = self.disable_leaf(message)
        if function == "migrate_leaf":
            response = self.migrate_leaf(message)
        if function == "create_leaf":
            response = self.add_leaf(message)

        if response is None:
            response = {
                "result": "failure",
                "message": "Unknown function"
            }

        if len(self.logs) > 0:
            response["logs"] = self.logs
            self.logs = []
        response["type"] = "result"
        return response

    @staticmethod
    def send_message(receiver, contents):
        try:
            http_client = tornado.httpclient.HTTPClient()
            post_data = json.dumps(contents)
            body = encode(post_data, receiver["secret"])
            response = json.loads(
                decode(http_client.fetch(
                    "http://{0}:{1}".format(receiver["host"], receiver["port"]),
                    method='POST',
                    body=body,
                    allow_ipv6=True
                ).body, receiver["secret"]))
            return response
        except Exception as e:
            return {
                "result": "failure",
                "message": e.message
            }

    @staticmethod
    def known_functions(message):
        return {
            "result": "functions",
            "functions": [
                {
                    "name": "status_report",
                    "description": "Получить информацию о состоянии компонентов системы",
                    "args": []
                },
                {
                    "name": "create_leaf",
                    "description": "Создать новый лист указанного типа",
                    "args": ["name", "type", "address"]
                },
                {
                    "name": "update_repository",
                    "description": "Обновить репозиторий",
                    "args": ["type"]
                },
                {
                    "name": "check_leaves",
                    "description": "Опросить все работающие листья",
                    "args": []
                },
                {
                    "name": "add_branch",
                    "description": "Добавить новую ветвь",
                    "args": ['name', 'host', 'port', 'secret', 'type']
                },
                {
                    "name": "enable_leaf",
                    "description": "Включить лист",
                    "args": ['name']
                },
                {
                    "name": "disable_leaf",
                    "description": "Отключить лист",
                    "args": ['name']
                },
                {
                    "name": "migrate_leaf",
                    "description": "Переместить лист на другую ветвь",
                    "args": ['name', 'destination']
                },
            ]
        }

    def login_user(self, message, user=None):
        if user:
            return {
                "type": "login",
                "result": "success",
                "message": "Already authenticated"
            }

        required_args = ['username', 'password']
        user_data = {}
        for arg in required_args:
            value = message.get(arg, None)
            if not value:
                return {
                    "result": "failure",
                    "message": "Argument '{0}' is missing".format(arg)
                }
            else:
                user_data[arg] = value

        if self.handler:
            client = pymongo.MongoClient(
                self.settings["mongo_host"],
                self.settings["mongo_port"]
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
        elif self.socket:
            return {
                "type": "login",
                "result": "error",
                "message": "Websocket authentication is not supported"
            }
        return {
            "type": "result",
            "result": "error",
            "message": "Failed to authenticate"
        }

    def check_leaves(self, message):
        client = pymongo.MongoClient(
            self.settings["mongo_host"],
            self.settings["mongo_port"]
        )

        leaf_names = []
        leaf_names_all = []
        for leaf in client.trunk.leaves.find({"active":True}):
            leaf_names.append(leaf["name"])
            leaf_names_all.append(leaf["name"])

        for branch in client.trunk.branches.find():
            self.log_event({
                "component": "branch",
                "name": branch["name"],
                "message": "Asking branch..."
            })
            response = self.send_message(
                branch,
                {
                    "function": "known_leaves"
                }
            )

            success = False
            failure = False

            if response["result"] == "success":
                for leaf in response["leaves"]:
                    # Лист есть в списке активных и в списке необработанных
                    if leaf["name"] in leaf_names_all and leaf["name"] in leaf_names:
                        success = success or True
                        self.log_event(leaf)
                        leaf_names.remove(leaf["name"])
                    # Лист есть в списке активных, но его уже обработали
                    elif leaf["name"] in leaf_names_all and leaf["name"] not in leaf_names:
                        self.log_event({
                            "warning": "Duplicate leaf found",
                            "component": "leaf",
                            "name": leaf["name"],
                            "response": leaf
                        }, type="warning")
                    # Листа нет в списке активных, но он активен на ветви
                    else:
                        self.log_event({
                            "warning": "This leaf shouldn't be active",
                            "component": "leaf",
                            "name": leaf["name"],
                            "response": leaf
                        }, type="warning")
            else:
                failure = failure or True
                self.log_event({
                    "error": "Failed to communicate with branch",
                    "component": "branch",
                    "name": branch["name"],
                    "response": response
                }, type="error")

            if success and not failure:
                return {
                    "result": "success",
                    "message": "All leaves responded"
                }
            elif success and failure:
                return {
                    "result": "warning",
                    "message": "Some leaves failed to respond"
                }
            else:
                return {
                    "result": "failure",
                    "message": "No response from leaves"
                }

    def status_report(self, message):
        client = pymongo.MongoClient(
            self.settings["mongo_host"],
            self.settings["mongo_port"]
        )

        for branch in client.trunk.branches.find():
            response = self.send_message(
                branch,
                {
                    "function": "status_report"
                }
            )

            if response["result"] == "success":
                if response["role"] == "branch":
                    branch_result = {
                        "result": "success",
                        "name": branch["name"],
                        "role": "branch"
                    }
                else:
                    branch_result = {
                        "result": "warning",
                        "name": branch["name"],
                        "role": response["role"],
                        "error": "Specified role 'branch' doesn't match response '{0}'".format(response["role"])
                    }
            else:
                branch_result = {
                    "result": "error",
                    "name": branch["name"],
                    "role": "branch",
                    "error": "Request failed. Is component secret key valid?",
                    "message": response["message"]
                }

            self.log_event(branch_result)

        for root in self.settings["roots"].keys():
            response = self.send_message(
                self.settings["roots"][root],
                {
                    "function": "status_report"
                }
            )

            if response["result"] == "success":
                if response["role"] == "roots":
                    root_result = {
                        "result": "success",
                        "name": root,
                        "role": "roots"
                    }
                else:
                    root_result = {
                        "result": "warning",
                        "name": root,
                        "role": response["role"],
                        "error": "Specified role 'roots' doesn't match response '{0}'".format(response["role"])
                    }
            else:
                root_result = {
                    "result": "error",
                    "name": root,
                    "role": "roots",
                    "error": "Request failed. Is component secret key valid?",
                    "message": response["message"]
                }

            self.log_event(root_result)

        for air in self.settings["air"].keys():
            response = self.send_message(
                self.settings["air"][air],
                {
                    "function": "status_report"
                }
            )

            if response["result"] == "success":
                if response["role"] == "air":
                    air_result = {
                        "result": "success",
                        "name": air,
                        "role": "air"
                    }
                else:
                    air_result = {
                        "result": "warning",
                        "name": air,
                        "role": response["role"],
                        "error": "Specified role 'air' doesn't match response '{0}'".format(response["role"])
                    }
            else:
                air_result = {
                    "result": "error",
                    "name": air,
                    "role": "air",
                    "error": "Request failed. Is component secret key valid?",
                    "message": response["message"]
                }

            self.log_event(air_result)

        return {"result": "success", "message": "Done"}

    def update_repo(self, message):
        # =========================================
        # Проверяем наличие требуемых аргументов
        # =========================================
        required_args = ['type']
        repo_data = {}
        for arg in required_args:
            value = message.get(arg, None)
            if not value:
                return {
                    "result": "failure",
                    "message": "Argument '{0}' is missing".format(arg)
                }
            else:
                repo_data[arg] = value
        result = {
            "success": [],
            "failure": [],
            "warning": [],
        }

        client = pymongo.MongoClient(
            self.settings["mongo_host"],
            self.settings["mongo_port"]
        )

        for branch in client.trunk.branches.find():
            if branch["type"] == repo_data["type"]:
                response = self.send_message(
                    branch,
                    {
                        "function": "update_repository"
                    }
                )
            result[response["result"]].append({
                "branch": branch["name"],
                "response": response
            })
        return result

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
            return {
                "result": "failure",
                "message": "unknown component type specified"
            }

        component = None
        try:
            if function_data['component'] == "branch":
                component = self.get_branch(function_data['name'])
            if function_data['component'] == "roots":
                component = self.get_root(function_data['name'])
            if function_data['component'] == "air":
                component = self.get_air(function_data['name'])
        except KeyError:
            return {
                "result": "failure",
                "message": "component with specified name not found"
            }

        if not component:
            return {
                "result": "failure",
                "message": "failed to get component: logic error, check code"  # реально не должно выпадать
            }

        post_data = {
            "function": function_data['function'],
        }
        arguments = json.loads(function_data['arguments'])

        if type(arguments) != dict:
            return {
                "result": "failure",
                "message": "function arguments should be provided in json-encoded dict"
            }

        for arg in arguments.keys():
            post_data[arg] = arguments[arg]

        response = self.send_message(component, post_data)
        return {
            "result": response["result"],
            "response": response
        }

    def add_leaf(self, message):
        # =========================================
        # Проверяем наличие требуемых аргументов
        # =========================================
        required_args = ['name', 'address', 'type']
        leaf_data = {}
        for arg in required_args:
            value = message.get(arg, None)
            if not value:
                return {
                    "result": "failure",
                    "message": "Argument '{0}' is missing".format(arg)
                }
            else:
                leaf_data[arg] = value
        leaf_settings = message.get("settings", "")
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
            return {
                "result": "failure",
                "message": "Leaf with name '{0}' already exists".format(leaf_data["name"])
            }
        leaf = leaves.find_one({"address": leaf_data["address"]})
        if leaf:
            return {
                "result": "failure",
                "message": "Leaf with address '{0}' already exists".format(leaf_data["address"])
            }
        # =========================================
        # Дополнительная проверка на наличие подходящей ветви
        # =========================================
        branch = self.get_branch(leaf_data["type"])
        if not branch:
            return {
                "result": "failure",
                "message": "No known branches of type '{0}'".format(leaf_data["type"])
            }
        # =========================================
        # Обращаемся к roots для создания новой базы
        # =========================================
        logs = []
        root = self.get_root()
        post_data = {
            "function": "prepare_database",
            "name": leaf_data["name"]
        }

        self.log_event({
            "status": "info",
            "component": "roots",
            "name": root["name"],
            "message": "Asking root to prepare database"
        })

        response = self.send_message(root, post_data)
        roots_response = response

        self.log_event({
            "status": "info",
            "component": "roots",
            "name": root["name"],
            "response": roots_response
        })

        if response["result"] != "success":
            result = {
                "result": "failure",
                "message": "Failed to get database settings",
                "details": response,
            }
            return logs

        env_for_leaf = json.dumps(response["env"])
        # =========================================
        # Обращаемся к branch для поднятия листа
        # =========================================
        post_data = {
            "function": "create_leaf",
            "name": leaf_data["name"],
            "env": env_for_leaf,
            "settings": leaf_settings,
            "initdb": "True"
        }

        self.log_event({
            "status": "info",
            "component": "branch",
            "name": branch["name"],
            "message": "Asking branch to start leaf"
        })

        response = self.send_message(branch, post_data)
        branch_response = response

        self.log_event({
            "status": "info",
            "component": "branch",
            "name": branch["name"],
            "response": branch_response
        })

        if response["result"] != "success":
            result = {
                "result": "failure",
                "message": "Failed to create leaf: {0}".format(response["message"])
            }
            return result
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

        self.log_event({
            "status": "info",
            "component": "air",
            "name": air["name"],
            "message": "Asking air to publish leaf"
        })

        response = self.send_message(air, post_data)

        self.log_event({
            "status": "info",
            "component": "air",
            "name": air["name"],
            "response": response
        })

        leaf = {
            "name": leaf_data["name"],
            "active": True,
            "type": leaf_data["type"],
            "address": leaf_data["address"],
            "branch": branch["name"],
            "port": branch_response["port"],
            "env": roots_response["env"],
            "settings": leaf_settings
        }
        leaves.insert(leaf)
        response = {
            "result": "success",
            "message": "Successfully added leaf '{0}'".format(leaf["name"])
        }
        return response

    def enable_leaf(self, message):
        # =========================================
        # Проверяем наличие требуемых аргументов
        # =========================================
        required_args = ['name']
        leaf_data = {}
        for arg in required_args:
            value = message.get(arg, None)
            if not value:
                return {
                    "result": "failure",
                    "message": "Argument '{0}' is missing".format(arg)
                }
            else:
                leaf_data[arg] = value
        # =========================================
        # Проверяем, есть ли лист с таким именем в базе
        # =========================================
        client = pymongo.MongoClient(
            self.settings["mongo_host"],
            self.settings["mongo_port"]
        )
        leaves = client.trunk.leaves
        leaf = leaves.find_one({"name": leaf_data["name"]})
        if not leaf:
            return {
                "result": "failure",
                "message": "Leaf with name '{0}' not found".format(leaf_data["name"])
            }
        if leaf["active"]:
            return {
                "result": "failure",
                "message": "Leaf with name '{0}' already enabled".format(leaf_data["address"])
            }
        # =========================================
        # Ищем подходящую ветку для листа
        # =========================================
        messages = []
        branch = client.trunk.branches.find_one({"name": leaf["branch"]})
        if not branch:
            branch = self.get_branch(leaf["type"])
            messages.append("Original branch not found; moving to new branch")
        if not branch:
            return {
                "result": "failure",
                "message": "No available branches of type '{0}'".format(leaf["type"])
            }
        # =========================================
        # Обращаемся к branch для поднятия листа
        # =========================================
        post_data = {
            "function": "create_leaf",
            "name": leaf["name"],
            "env": leaf["env"],
            "settings": leaf.get("settings", {})
        }
        response = self.send_message(branch, post_data)
        branch_response = response
        if response["result"] != "success":
            return {
                "result": "failure",
                "message": "Failed to create leaf: {0}".format(response["message"])
            }
        # =========================================
        # Обращаемся к air для публикации листа
        # =========================================
        air = self.get_air()
        post_data = {
            "function": "publish_leaf",
            "name": leaf["name"],
            "address": leaf["address"],
            "host": response["host"],
            "port": response["port"]
        }
        response = self.send_message(air, post_data)
        leaves.update(
            {"name": leaf_data["name"]},
            {
                "name": leaf["name"],
                "active": True,
                "type": leaf["type"],
                "address": leaf["address"],
                "branch": leaf["branch"],
                "port": branch_response["port"],
                "env": leaf["env"]
            },
            upsert=True,
            multi=False
        )
        return {
            "result": "success",
            "message": "Re-enabled leaf '{0}'".format(leaf["name"])
        }

    def disable_leaf(self, message):
        # =========================================
        # Проверяем наличие требуемых аргументов
        # =========================================
        required_args = ['name']
        leaf_data = {}
        for arg in required_args:
            value = message.get(arg, None)
            if not value:
                return {
                    "result": "failure",
                    "message": "Argument '{0}' is missing".format(arg)
                }
            else:
                leaf_data[arg] = value

        client = pymongo.MongoClient(
            self.settings["mongo_host"],
            self.settings["mongo_port"]
        )
        leaves = client.trunk.leaves
        leaf = leaves.find_one({"name": leaf_data["name"]})
        if not leaf:
            return {
                "result": "failure",
                "message": "Leaf with name '{0}' not found".format(leaf_data["name"])
            }
        if not leaf["active"]:
            return {
                "result": "failure",
                "message": "Leaf with name '{0}' already disabled".format(leaf_data["name"])
            }
        # =========================================
        # Обращаемся к branch для удаления листа
        # =========================================
        branch = client.trunk.branches.find_one({"name": leaf["branch"]})
        if not branch:
            return {
                "result": "failure",
                "message": "Internal server error: leaf '{0}' running on unknown branch".format(leaf_data["name"])
            }
        post_data = {
            "function": "delete_leaf",
            "name": leaf["name"]
        }
        response = self.send_message(branch, post_data)

        if response["result"] != "success":
            return {
                "result": "failure",
                "message": "Failed to delete leaf: {0}".format(response["message"])
            }
        # =========================================
        # Обращаемся к air для де-публикации листа
        # =========================================
        air = self.get_air()
        post_data = {
            "function": "unpublish_leaf",
            "name": leaf["name"]
        }
        response = self.send_message(air, post_data)
        leaves.update(
            {"name": leaf_data["name"]},
            {
                "name": leaf["name"],
                "active": False,
                "type": leaf["type"],
                "address": leaf["address"],
                "branch": leaf["branch"],
                "port": leaf["port"],
                "env": leaf["env"]
            },
            upsert=False,
            multi=False
        )
        return {
            "result": "success",
            "message": "Disabled leaf '{0}'".format(leaf["name"])
        }

    def migrate_leaf(self, message):
        # =========================================
        # Проверяем наличие требуемых аргументов
        # =========================================
        required_args = ['name', 'destination']
        leaf_data = {}
        for arg in required_args:
            value = message.get(arg, None)
            if not value:
                return {
                    "result": "failure",
                    "message": "Argument '{0}' is missing".format(arg)
                }
            else:
                leaf_data[arg] = value
        # =========================================
        # Ищем лист в базе
        # =========================================
        client = pymongo.MongoClient(
            self.settings["mongo_host"],
            self.settings["mongo_port"]
        )
        leaves = client.trunk.leaves
        leaf = leaves.find_one({"name": leaf_data["name"]})
        if not leaf:
            return {
                "result": "failure",
                "message": "Leaf with name {0} not found".format(leaf_data["name"])
            }

        if leaf["branch"] == leaf_data["destination"]:
            return {
                "result": "warning",
                "message": "Leaf is already on branch '{0}'".format(leaf["branch"])
            }
        # =========================================
        # Ищем ветви, старую и новую
        # =========================================
        branches = client.trunk.branches
        old_branch = branches.find_one({"name": leaf["branch"]})
        new_branch = branches.find_one({"name": leaf_data["destination"]})

        if new_branch["type"] != leaf["type"]:
            return {
                "result": "failure",
                "message": "Can't move leaf with type '{0}' to branch with type '{1}'".format(leaf["type"], new_branch["type"])
            }

        if not new_branch:
            return {
                "result": "failure",
                "message": "Destination branch not found"
            }
        if not old_branch:
            return {
                "result": "failure",
                "message": "Internal server error: source branch '{0}'' not found".format(leaf["branch"])
            }
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
            return {
                "result": "failure",
                "message": "Failed to create leaf: {0}".format(response["message"])
            }
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
            return {
                "result": "failure",
                "message": "Failed to publish leaf: {0}".format(response["message"])
            }
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
            return {
                "result": "failure",
                "message": "Failed to delete leaf: {0}".format(response["message"])
            }

        leaves.update(
            {"name": leaf_data["name"]},
            {
                "name": leaf["name"],
                "active": True,
                "type": leaf["type"],
                "address": leaf["address"],
                "branch": leaf_data["destination"],
                "port": new_branch_response["port"],
                "env": leaf["env"]
            },
            upsert=False,
            multi=False
        )
        return {
            "result": "success",
            "message": "Moved leaf to {0}".format(leaf_data["destination"])
        }

    def add_branch(self, message):
        # =========================================
        # Проверяем наличие требуемых аргументов
        # =========================================
        required_args = ['name', 'host', 'port', 'secret', 'type']
        branch_data = {}
        for arg in required_args:
            value = message.get(arg, None)
            if not value:
                return {
                    "result": "failure",
                    "message": "Argument '{0}' is missing".format(arg)
                }
            else:
                branch_data[arg] = value
        # =========================================
        # Проверяем, нет ветви с таким именем в базе
        # =========================================
        client = pymongo.MongoClient(
            self.settings["mongo_host"],
            self.settings["mongo_port"]
        )
        branches = client.trunk.branches
        branch = branches.find_one({"name": branch_data["name"]})
        if branch:
            return {
                "result": "failure",
                "message": "Branch with name '{0}' already exists".format(branch_data["name"])
            }
        # =========================================
        # Сохраняем ветку в базе
        # =========================================
        branch = {
            "name": branch_data["name"],
            "type": branch_data["type"],
            "host": branch_data["host"],
            "port": branch_data["port"],
            "secret": branch_data["secret"]
        }
        branches.insert(branch)
        return {
            "result": "success",
            "message": "Branch '{0}' successfully added".format(branch_data["name"])
        }

    def get_branches(self, message):
        client = pymongo.MongoClient(
            self.settings["mongo_host"],
            self.settings["mongo_port"]
        )

        return {
            "result": "success",
            "branches": [branch for branch in client.trunk.branches.find()]
        }

    def modify_branch(self, message):
        # =========================================
        # Проверяем наличие требуемых аргументов
        # =========================================
        required_args = ['name', "args"]
        branch_data = {}
        for arg in required_args:
            value = message.get(arg, None)
            if not value:
                return {
                    "result": "failure",
                    "message": "Argument '{0}' is missing".format(arg)
                }
            else:
                branch_data[arg] = value
        # =========================================
        # Проверка на наличие ветви с таким именем
        # =========================================
        client = pymongo.MongoClient(
            self.settings["mongo_host"],
            self.settings["mongo_port"]
        )
        if not client.trunk.branches.find_one({"name": branch_data["name"]}):
            return {
                "result": "failure",
                "component": "branch",
                "message": "Branch with specified name not found"
            }
        # =========================================
        # Гордо переписываем все, что сказано
        # =========================================
        client.trunk.branches.update(
            {"name": branch_data["name"]},
            {
                "$set": branch_data["args"],
            },
            upsert=False,
            multi=False
        )
        return {
            "result": "success",
            "message": "Successfully updated branch"
        }

    def get_branch(self, branch_type):
        client = pymongo.MongoClient(
            self.settings["mongo_host"],
            self.settings["mongo_port"]
        )
        branches = client.trunk.branches
        return branches.find_one({"type": branch_type})

    def get_root(self, name="main"):
        root = self.settings["roots"][name]
        root["name"] = name
        return root

    def get_air(self, name="main"):
        air = self.settings["air"][name]
        air["name"] = name
        return air