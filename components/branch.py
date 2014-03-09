# -*- coding: utf-8 -*-
from __future__ import print_function
import os
import tornado.web
from subprocess import CalledProcessError, check_output, STDOUT
from components.leaf import Leaf
from components.common import log_message, check_arguments, \
    run_parallel, LogicError, get_connection
import traceback
import psutil


class Branch(tornado.web.Application):
    def __init__(self, settings_dict, **settings):
        super(Branch, self).__init__(**settings)
        self.settings = settings_dict
        self.leaves = []
        
        client = get_connection(
            self.settings["mongo_host"],
            self.settings["mongo_port"],
            "admin",
            "password"
        )
        self.fastrouters = []
        for air in client.trunk.components.find({"type": "air"}):
            self.fastrouters.append("{0}:{1}".format(air["ip"], air["fastrouter"]))

        log_message("I know these fastrouters:{0}".format(self.fastrouters), 
                    component="Branch")

        self.functions = {
            "restart_leaf": self.restart_leaf,
            "get_leaf_logs": self.get_leaf_logs,
            "status_report": self.status_report,
            "known_leaves": self.known_leaves,
            "update_repository": self.update_repo,
            "update_state": self.update_state,
            "status_report": self.status_report
        }

        self.init_leaves()

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
            host=self.settings["host"],
            env=leaf.get("env", {}),
            settings=leaf.get("settings", {}),
            fastrouters=self.fastrouters,
            keyfile=self.settings.get("keyfile"),
            address=leaf.get("address"),
            static=self.settings.get("static")
        )
        try:
            new_leaf.start()
            self.leaves.append(new_leaf)
            new_leaf.init_database()
        except Exception:
            raise LogicError("Start failed: {0}".format(traceback.format_exc()))

    def status_report(self, message):
        # Память
        mem = psutil.virtual_memory()
        swap = psutil.swap_memory()
        # Нагрузка
        load_1, load_5, load_15 = os.getloadavg()
        # Аптайм
        try:
            f = open("/proc/uptime")
            contents = f.read().split()
            f.close()

            total_seconds = float(contents[0])

            MINUTE = 60
            HOUR = MINUTE * 60
            DAY = HOUR * 24

            days = int(total_seconds / DAY)
            hours = int((total_seconds % DAY) / HOUR)
            minutes = int((total_seconds % HOUR) / MINUTE)
            seconds = int(total_seconds % MINUTE)
        except:
            days = 0
            hours = 0
            minutes = 0
            seconds = 0

        measurements = {
            "mem_total": mem.total / (1024 * 1024),
            "mem_used": (mem.used - mem.buffers - mem.cached) / (1024 * 1024),
            "mem_cached": (mem.buffers + mem.cached) / (1024 * 1024),
            "mem_free": mem.free / (1024 * 1024),
            "swap_total": swap.total / (1024 * 1024),
            "swap_used": swap.used / (1024 * 1024),
            "swap_free": swap.free / (1024 * 1024),
            "load_1": load_1,
            "load_5": load_5,
            "load_15": load_15,
            "uptime_days": days,
            "uptime_hours": hours,
            "uptime_minutes": minutes,
            "uptime_seconds": seconds
        }
        return {
            "result": "success",
            "message": "Working well",
            "role": "branch",
            "measurements": measurements
        }

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
                    ".format(to_remove, to_update, to_append, current_leaves),
                    component="Branch")

        for leaf in self.leaves:
            if leaf.name in to_remove:
                leaf.stop()
                self.leaves.remove(leaf)

        for leaf in db_leaves:
            if leaf["name"] in to_update:
                leaf_running = self.get_leaf(leaf["name"])
                if leaf.get("settings", {}) != leaf_running.settings or \
                   leaf["env"] != leaf_running.launch_env:
                    log_message("Leaf {0} configuration changed, reloading\
                                ".format(leaf["name"]), component="Branch")
                    leaf_running.settings = leaf["settings"]
                    leaf_running.env = leaf["env"]
                    leaf_running.restart()
            elif leaf["name"] in to_append:
                log_message("Adding leaf {0}".format(leaf["name"]),
                            component="Branch")
                self.add_leaf(leaf)

        return {
            "result": "success"
        }

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

            new_leaf = Leaf(
                name=leaf["name"],
                chdir=self.settings["chdir"],
                executable=self.settings["executable"],
                host=self.settings["host"],
                env=leaf.get("env", {}),
                settings=leaf.get("settings", {}),
                fastrouters=self.fastrouters,
                keyfile=self.settings.get("keyfile", None),
                address=leaf.get("address"),
                static=self.settings.get("static")
            )
            new_leaf.start()
            self.leaves.append(new_leaf)

    def cleanup(self):
        log_message("Shutting down leaves...", component="Branch")
        run_parallel([leaf.stop for leaf in self.leaves])

    def known_leaves(self, message):
        known_leaves = []
        for leaf in self.leaves:
            known_leaves.append({
                "name": leaf.name,
                "port": leaf.port,
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
            leaf.graceful_restart()

        return result
