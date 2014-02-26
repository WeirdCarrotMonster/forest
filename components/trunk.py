# -*- coding: utf-8 -*-
import tornado.web
import simplejson as json
import tornado.httpclient
import tornado.template
import pymongo
from components.shadow import encode, decode
from components.common import check_arguments, get_connection, \
    LogicError, Warning
import hashlib


class Trunk(tornado.web.Application):
    def __init__(self, settings_dict, **settings):
        super(Trunk, self).__init__(**settings)
        self.settings = settings_dict
        self.settings["cookie_secret"] = 'asdfasdf'
        self.socket = None
        self.handler = None
        self.logs = []
        self.safe_urls = {
            "login": "html/login.html",
        }
        self.auth_urls = {
            "dashboard": "html/dashboard.html",
            "leaves": "html/leaves.html",
            "fauna": "html/fauna.html"
        }

        self.functions = {
            # Обработка состояний сервера
            "dashboard_stats": self.dashboard_stats,
            "status_report": self.status_report,
            "update_repository": self.update_repo,
            "check_leaves": self.check_leaves,
            "get_memory_logs": self.get_memory_logs,
            # Работа с ветвями
            "add_branch": self.add_branch,
            "modify_branch": self.modify_branch,
            "list_branches": self.list_branches,
            "add_owl": self.add_owl,
            # Работа с листьями
            "enable_leaf": self.enable_leaf,
            "disable_leaf": self.disable_leaf,
            "migrate_leaf": self.migrate_leaf,
            "create_leaf": self.add_leaf,
            "rehost_leaf": self.rehost_leaf,
            "change_settings": self.change_settings,
            "get_leaf_logs": self.get_leaf_logs
        }

    def log_event(self, event, event_type="info"):
        if self.socket:
            event["type"] = event_type
            self.socket.send_message(event)
        else:
            self.logs.append(event)

    def process_page(self, page, user):
        if page in self.safe_urls.keys():
            return self.safe_urls[page]

        if page in self.auth_urls.keys() and user:
            return self.auth_urls[page]

        if page in self.auth_urls.keys() and not user:
            raise Exception("Who's there?")

        raise Exception("I'm sorry, Dave. I'm afraid I can't do that.")

    def process_message(self, message, socket=None, handler=None, user=None):
        self.socket = socket
        self.handler = handler
        self.logs = []
        response = None
        function = message.get('function', None)

        if function == "login_user":
            response = self.login_user(message, user=user)
            return response

        if not user:
            raise LogicError("Not authenticated")

        # Далее - функции только для залогиненых
        if not function in self.functions:
            raise LogicError("No function or unknown one called")

        response = self.functions[function](message)
        if len(self.logs) > 0:
            response["logs"] = self.logs
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
                    "http://{0}:{1}".format(
                        receiver["host"], receiver["port"]),
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

    def log_stats(self):
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

        log = {}

        for branch in client.trunk.branches.find():
            response = self.send_message(
                branch,
                {
                    "function": "known_leaves"
                }
            )

            if response["result"] == "success":
                for leaf in response["leaves"]:
                    log[leaf["name"]] = leaf["mem"]
            else:
                pass

        logs_document = client.trunk.logs.find_one({"type": "memory"})
        if not logs_document:
            client.trunk.logs.insert({"type": "memory", "values": []})
            logs = []
        else:
            logs = logs_document["values"]

        if len(logs) > 100:
            logs = logs[-99:]

        logs.append(log)
        client.trunk.logs.update(
            {"type": "memory"}, {"$set": {"values": logs}})

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

    def dashboard_stats(self, message):
        client = get_connection(
            self.settings["mongo_host"],
            self.settings["mongo_port"],
            "admin",
            "password"
        )

        loads = []
        for owl in client.trunk.owls.find():
            response = self.send_message(
                owl,
                {
                    "function": "status_report"
                }
            )
            if response["result"] == "success":
                one_load = response["mesaurements"]
                one_load["name"] = owl["name"]
                one_load["verbose_name"] = owl["verbose_name"]
                one_load["result"] = "success"
                one_load["ip"] = owl["host"]
                loads.append(one_load)
            else:
                loads.append({
                    "name": owl["name"],
                    "result": "error",
                    "ip": owl["host"]
                })

        return {
            "result": "success",
            "message": "Done",
            "servers": loads
        }

    def status_report(self, message):
        client = get_connection(
            self.settings["mongo_host"],
            self.settings["mongo_port"],
            "admin",
            "password"
        )

        loads = []
        for owl in client.trunk.owls.find():
            response = self.send_message(
                owl,
                {
                    "function": "status_report"
                }
            )
            if response["result"] == "success":
                one_load = response["mesaurements"]
                one_load["name"] = owl["name"]
                one_load["verbose_name"] = owl["verbose_name"]
                one_load["result"] = "success"
                loads.append(one_load)
            else:
                loads.append({
                    "name": owl["name"],
                    "result": "error"
                })

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
                        "error": "Specified role 'branch' doesn't \
                                  match response '{0}'".format(response["role"])
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
                        "error": "Specified role 'roots' doesn't \
                                  match response '{0}'".format(response["role"])
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
                        "error": "Specified role 'air' doesn't \
                                  match response '{0}'".format(response["role"])
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

        return {
            "result": "success",
            "message": "Done",
            "loads": loads
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
                        "function": "update_repository"
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

        # Записываем лист в базе
        leaves.insert({
            "name": leaf_data["name"],
            "active": True,
            "type": leaf_data["type"],
            "address": leaf_data["address"],
            "branch": branch["name"],
            "settings": leaf_settings
        })
        # На данном этапе у листа отсутствует порт и настройки базы
        # Они будут заполнены позднее

        # Обращаемся к roots для создания новой базы
        root = self.get_root()
        response = self.request_update(root)

        self.log_event({
            "status": "info",
            "component": "roots",
            "name": root["name"],
            "response": response
        })

        # Посылаем branch сигнал об обновлении состояния
        self.log_event({
            "status": "info",
            "component": "branch",
            "name": branch["name"],
            "message": "Asking branch to start leaf"
        })

        response = self.request_update(branch)

        self.log_event({
            "status": "info",
            "component": "branch",
            "name": branch["name"],
            "response": response
        })

        # Обращаемся к air для публикации листа
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

        # Обращаемся к branch для обновления состояния
        self.request_update(branch)

        # Обращаемся к air для публикации листа
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

        # Обращаемся к branch для удаления листа
        branch = client.trunk.branches.find_one({"name": leaf["branch"]})
        if branch:
            self.request_update(branch)

        # Обращаемся к air для де-публикации листа
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
        branches = client.trunk.branches
        old_branch = branches.find_one({"name": leaf["branch"]})
        new_branch = branches.find_one({"name": leaf_data["destination"]})

        if new_branch["type"] != leaf["type"]:
            raise LogicError("Can't move leaf with type \
                             '{0}' to branch with type '{1}'\
                             ".format(leaf["type"], new_branch["type"]))

        if not new_branch:
            raise LogicError("Destination branch not found")

        leaves.update(
            {"name": leaf_data["name"]},
            {
                "$set": {"branch": new_branch["name"]},
                "$unset": {"port": 1}
            }
        )

        # Обращаемся к новому branch'у для переноса листа
        if old_branch:
            self.send_message(old_branch, {"function": "update_state"})
        self.send_message(new_branch, {"function": "update_state"})

        # Обращаемся к air для публикации листа
        air = self.get_air()
        self.send_message(air, {"function": "update_state"})

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
        air = self.get_air()
        self.send_message(air, {"function": "update_state"})

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
            # Обновляем настройки на самой ветви
            branch = client.trunk.branches.find_one({"name": leaf["branch"]})
            if not branch:
                raise LogicError("Internal error: \
                                  leaf hosted on unknown branch")

            self.send_message(branch, {"function": "update_state"})

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

        branch = client.trunk.branches.find_one({"name": leaf["branch"]})
        if not branch:
            raise LogicError("Leaf hosted on unknown branch")

        post_data = {
            "function": "get_leaf_logs",
            "name": leaf["name"]
        }
        response = self.send_message(branch, post_data)
        if response["result"] != "success":
            raise LogicError("Failed to get logs from branch")

        return {
            "result": "success",
            "logs": response["logs"]
        }

    def add_branch(self, message):
        # Проверяем наличие требуемых аргументов
        branch_data = check_arguments(
            message,
            ['name', 'host', 'port', 'secret', 'type']
        )

        # Проверяем, нет ветви с таким именем в базе
        client = get_connection(
            self.settings["mongo_host"],
            self.settings["mongo_port"],
            "admin",
            "password"
        )
        branches = client.trunk.branches
        branch = branches.find_one({"name": branch_data["name"]})
        if branch:
            raise LogicError("Branch with name \
                              '{0}' already exists".format(branch_data["name"]))

        # Сохраняем ветку в базе
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
            "message": "Branch '{0}' \
                        successfully added".format(branch_data["name"])
        }

    def update_air(self):
        air = self.get_air()
        return self.send_message(air, {"function": "update_state"})

    def request_update(self, component):
        return self.send_message(component, {"function": "update_state"})

    def add_owl(self, message):
        # Проверяем наличие требуемых аргументов
        owl = check_arguments(
            message,
            ['name', 'verbose_name', 'host', 'port', 'secret']
        )

        # Проверяем, нет ли филина с таким именем в базе
        client = get_connection(
            self.settings["mongo_host"],
            self.settings["mongo_port"],
            "admin",
            "password"
        )
        owls = client.trunk.owls
        if owls.find_one({"name": owl["name"]}):
            return {
                "result": "failure",
                "message": "Owl with name '{0}' \
                            already exists".format(owl["name"])
            }

        # Сохраняем филина в базе
        owls.insert(owl)
        return {
            "result": "success",
            "message": "Owl '{0}' successfully added".format(owl["name"])
        }

    def list_branches(self, message):
        client = pymongo.MongoClient(
            self.settings["mongo_host"],
            self.settings["mongo_port"]
        )

        branches = []
        for branch in client.trunk.branches.find():
            branches.append({"name": branch["name"], "type": branch["type"]})

        return {
            "result": "success",
            "branches": branches
        }

    def modify_branch(self, message):
        # =========================================
        # Проверяем наличие требуемых аргументов
        # =========================================
        branch_data = check_arguments(message, ['name', "args"])

        # =========================================
        # Проверка на наличие ветви с таким именем
        # =========================================
        client = get_connection(
            self.settings["mongo_host"],
            self.settings["mongo_port"],
            "admin",
            "password"
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
            }
        )
        return {
            "result": "success",
            "message": "Successfully updated branch"
        }

    def read_events(self):
        client = get_connection(
            self.settings["mongo_host"],
            self.settings["mongo_port"],
            "admin",
            "password"
        )
        need_air_restart = False
        accepted = []
        for event in client.trunk.events.find({"to": "trunk"}):
            accepted.append(event)
            if event["message"] == "ports_reassigned":
                need_air_restart |= True

        for event in accepted:
            client.trunk.events.remove({"_id": event["_id"]})

        # TODO: перенести перезапуск прокси в отдельный метод
        if need_air_restart:
            air = self.get_air()
            self.send_message(air, {"function": "update_state"})

    def get_branch(self, branch_type):
        client = get_connection(
            self.settings["mongo_host"],
            self.settings["mongo_port"],
            "admin",
            "password"
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
