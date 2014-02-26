# -*- coding: utf-8 -*-
from __future__ import print_function
import os
import tornado.web
from subprocess import CalledProcessError, check_output, STDOUT
from components.leaf import Leaf
from components.common import log_message, check_arguments, \
    run_parallel, LogicError, get_connection
import traceback


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
            env=leaf["env"],
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
        db_leaves = client.trunk.leaves.find({
            "branch": self.settings["name"],
            "active": True
        })
        db_leaves_names = [leaf["name"] for leaf in db_leaves]

        # Сравниваем списки листьев
        # Выбираем все листы, которые есть локально, но не
        # указаны в базе и выключаем их
        to_remove = list(set(current_leaves) - set(db_leaves_names))

        for leaf in self.leaves:
            if leaf.name in to_remove:
                leaf.stop()
                self.leaves.remove(leaf)

        # Обрабатываем все листья, назначенные на данную ветвь
        for leaf in db_leaves:
            if leaf["name"] in current_leaves:
                # Лист уже работает
                # Перечитываем конфиг и сравниваем с текущим,
                # при необходимости перезапускаем лист
                leaf_running = self.get_leaf(leaf["name"])
                if leaf["settings"] != leaf_running.settings or \
                   leaf["env"] != leaf_running.env:
                    leaf_running.settings = leaf["settings"]
                    leaf_running.env = leaf["env"]
                    leaf_running.restart()
            else:
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
        for leaf in leaves:
            log_message("Found leaf {0} in configuration".format(
                leaf["name"]),
                component="Branch"
            )
            new_leaf = Leaf(
                name=leaf["name"],
                chdir=self.settings["chdir"],
                executable=self.settings["executable"],
                fcgi_host=self.settings["host"],
                fcgi_port=leaf["port"],
                pidfile=os.path.join(self.settings["pid_dir"],
                                     leaf["name"] + '.pid'),
                logfile=os.path.join(self.settings["log_dir"],
                                     leaf["name"] + '.log'),
                env=leaf.get("env", {}),
                settings=leaf.get("settings", {})
            )
            try:
                self.settings["port_range"].remove(new_leaf.fcgi_port)
            except ValueError:
                # Порт не в списке. Стабильности ради делаем НИЧЕГО.
                pass
            new_leaf.start()
            self.leaves.append(new_leaf)

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
