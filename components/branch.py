# -*- coding: utf-8 -*-
from __future__ import print_function
import os
import tornado.web
from subprocess import CalledProcessError, check_output, STDOUT
from components.leaf import Leaf
from components.common import log_message, check_arguments, \
    run_parallel, LogicError, get_connection
import traceback
import time


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
            "restart_leaf": self.restart_leaf,
            "get_leaf_logs": self.get_leaf_logs,
            "status_report": self.status_report,
            "known_leaves": self.known_leaves,
            "update_repository": self.update_repo,
            "update_state": self.update_state
        }

    def process_message(self, message):
        function = message.get('function', None)

        if not function in self.functions:
            raise LogicError("No function or unknown one called")

        return self.functions[function](message)

    def get_leaf(self, leaf_name):
        for leaf in self.leaves:
            if leaf.name == leaf_name:
                return leaf
        return None

    def add_leaf(self, leaf):
        new_leaf = Leaf(
            name=leaf["name"],
            chdir=self.settings["chdir"],
            executable=self.settings["executable"],
            fcgi_host=self.settings["host"],
            fcgi_port=self.get_port(),
            pidfile=os.path.join(
                self.settings["pid_dir"],
                leaf["name"] + '.pid'
            ),
            logfile=os.path.join(
                self.settings["log_dir"],
                leaf["name"] + '.log'
            ),
            env=leaf.get("env", {}),
            settings=leaf["settings"]
        )
        try:
            new_leaf.start()
            self.leaves.append(new_leaf)
            new_leaf.init_database()
        except Exception:
            self.return_port(new_leaf.fcgi_port)
            raise LogicError("Start failed: {0}".format(traceback.format_exc()))
        else:
            # Лист успешно запущен.
            # Записываем порт, на котором он активирован
            client = get_connection(
                self.settings["mongo_host"],
                self.settings["mongo_port"],
                "admin",
                "password"
            )
            client.trunk.leaves.update(
                {"name": leaf["name"]},
                {"$set": {"port": new_leaf.fcgi_port}}
            )

    def update_state(self, message):
        client = get_connection(
            self.settings["mongo_host"],
            self.settings["mongo_port"],
            "admin",
            "password"
        )
        # Составляем списки имеющихся листьев и требуемых
        current_leaves = [leaf.name for leaf in self.leaves]
        db_leaves = [leaf for leaf in client.trunk.leaves.find({
            "branch": self.settings["name"],
            "active": True
        })]
        db_leaves_names = [leaf["name"] for leaf in db_leaves]

        # Сравниваем списки листьев
        # Выбираем все листы, которые есть локально, но не
        # указаны в базе и выключаем их
        to_remove = list(set(current_leaves) - set(db_leaves_names))
        to_update = list(set(current_leaves) & set(db_leaves_names))
        to_append = list(set(db_leaves_names) - set(current_leaves))

        log_message("Triggering update", component="Branch")
        log_message("Doing following shit:\n\
                     to_remove: {0}\n\
                     to_update: {1}\n\
                     to_append: {2}\n\
                     current_leaves: {3}\
                    ".format(to_remove, to_update, to_append),
                    component="Branch")

        # Удаляем те, что должны быть випилены
        for leaf in self.leaves:
            if leaf.name in to_remove:
                leaf.stop()
                self.leaves.remove(leaf)

        # Перепроверяем данные у тех, что не изменились
        for leaf in to_update:
            leaf_running = self.get_leaf(leaf["name"])
            if leaf["settings"] != leaf_running.settings or \
               leaf["env"] != leaf_running.env:
                log_message("Leaf {0} configuration changed, reloading\
                            ".format(leaf["name"]), component="Branch")
                leaf_running.settings = leaf["settings"]
                leaf_running.env = leaf["env"]
                leaf_running.restart()

        # Добавляем те, что отсутствуют в данный момент
        for leaf in db_leaves:
            if leaf["name"] in to_append:
                log_message("Adding leaf {0}".format(leaf["name"]),
                            component="Branch")
                self.add_leaf(leaf)

        return {
            "result": "success"
        }

    def get_port(self):
        return self.settings["port_range"].pop()

    def return_port(self, port):
        self.settings["port_range"].append(port)

    def init_leaves(self):
        client = get_connection(
            self.settings["mongo_host"],
            self.settings["mongo_port"],
            "admin",
            "password"
        )
        leaves = client.trunk.leaves.find({
            "branch": self.settings["name"],
            "active": True
        })

        ports_reassigned = False
        for leaf in leaves:
            log_message("Found leaf {0} in configuration\nPort: {1}".format(
                leaf["name"], leaf.get("port")),
                component="Branch"
            )
            port = leaf.get("port")
            if port in self.settings["port_range"]:
                # Активируем на порту, который попадает в диапазон и свободен
                self.settings["port_range"].remove(port)
            else:
                port = self.get_port()
                client.trunk.leaves.update(
                    {"name": leaf["name"]},
                    {"$set": {"port": port}}
                )
                ports_reassigned |= True

            new_leaf = Leaf(
                name=leaf["name"],
                chdir=self.settings["chdir"],
                executable=self.settings["executable"],
                fcgi_host=self.settings["host"],
                fcgi_port=port,
                pidfile=os.path.join(
                    self.settings["pid_dir"],
                    leaf["name"] + '.pid'),
                logfile=os.path.join(
                    self.settings["log_dir"],
                    leaf["name"] + '.log'),
                env=leaf.get("env", {}),
                settings=leaf.get("settings", {})
            )
            new_leaf.start()
            self.leaves.append(new_leaf)

        if ports_reassigned:
            client.trunk.events.insert({
                "to": "trunk",
                "from": "branch",
                "message": "ports_reassigned"
            })

    def shutdown_leaves(self):
        log_message("Shutting down leaves...", component="Branch")
        run_parallel([leaf.stop for leaf in self.leaves])

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

    def restart_leaf(self, message):
        leaf_data = check_arguments(message, ["name"])
        leaf = self.get_leaf(leaf_data["name"])
        if leaf:
            leaf.restart()
        else:
            raise LogicError("Leaf with name {0} not found".format(
                leaf_data["name"]))

        log_message("Restarting leaf '{0}'".format(
            leaf_data["name"]), component="Branch")

        return {
            "result": "success",
            "message": "restarted leaf {0}".format(leaf_data["name"])
        }

    def get_leaf_logs(self, message):
        leaf_data = check_arguments(message, ["name"])

        logs = None
        leaf = self.get_leaf(leaf_data["name"])
        if leaf:
            logs = leaf.get_logs()
        else:
            raise LogicError("Leaf with name {0} not found".format(
                leaf_data["name"]))

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
                raise LogicError("configuration error: unknown repository type")
        except CalledProcessError:
            result = {
                "result": "failure",
                "message": traceback.format_exc()
            }

        run_parallel([leaf.update_database for leaf in self.leaves])

        for leaf in self.leaves:
            leaf.restart()

        return result
