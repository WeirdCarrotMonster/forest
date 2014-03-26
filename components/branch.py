# -*- coding: utf-8 -*-
from __future__ import print_function
import os
from subprocess import CalledProcessError, check_output, STDOUT
from components.leaf import Leaf
from components.common import log_message, check_arguments, \
    run_parallel, LogicError, get_settings_connection
import traceback
import psutil


class Branch():
    def __init__(self, settings):
        self.settings = settings
        self.leaves = []

        client = get_settings_connection(self.settings)
        self.fastrouters = []
        components = client.trunk.components
        for component in components.find({"roles.air": {"$exists": True}}):
            host = component["host"]
            port = component["roles"]["air"]["fastrouter"]
            self.fastrouters.append("{0}:{1}".format(host, port))
        self.init_leaves()

    def __get_assigned_leaves(self):
        client = get_settings_connection(self.settings)
        return client.trunk.leaves.find({
            "branch": self.settings["name"],
            "active": True
        })

    def get_leaf(self, leaf_name):
        for leaf in self.leaves:
            if leaf.name == leaf_name:
                return leaf
        return None

    def add_leaf(self, leaf):
        # TODO: переписывать адрес MySQL-сервера, выбирая его из базы
        repo = self.settings["species"][leaf.get("type")]
        new_leaf = Leaf(
            name=leaf["name"],
            chdir=repo["path"],
            executable=repo["executable"],
            host=self.settings["host"],
            env=leaf.get("env", {}),
            settings=leaf.get("settings", {}),
            fastrouters=self.fastrouters,
            keyfile=self.settings.get("keyfile", None),
            address=leaf.get("address"),
            static=repo["static"],
            leaf_type=leaf.get("type")
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
        # Составляем списки имеющихся листьев и требуемых
        current_leaves = [leaf.name for leaf in self.leaves]
        db_leaves = [leaf for leaf in self.__get_assigned_leaves()]
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

    def init_leaves(self):
        for leaf in self.__get_assigned_leaves():
            log_message("Found leaf {0} in configuration".format(
                leaf["name"]),
                component="Branch"
            )
            self.add_leaf(leaf)

    def cleanup(self):
        log_message("Shutting down leaves...", component="Branch")
        run_parallel([leaf.stop for leaf in self.leaves])

    def known_leaves(self, message):
        known_leaves = []
        for leaf in self.leaves:
            known_leaves.append({
                "name": leaf.name,
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
        check_arguments(message, ["type"])
        repo_name = message["type"]

        if not repo_name in self.settings["species"].keys():
            return {
                "result": "failure",
                "message": "Unknown repo type"
            }

        repo_path = self.settings["species"][repo_name]["path"]
        repo_type = self.settings["species"][repo_name]["type"]

        try:
            if repo_type == "git":
                cmd = [
                    "git",
                    "--git-dir={0}/.git".format(repo_path),
                    "--work-tree={0}".format(repo_path),
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

        to_update = [leaf for leaf in self.leaves if leaf.type == repo_type]

        run_parallel([leaf.update_database for leaf in to_update])

        for leaf in to_update:
            leaf.graceful_restart()

        return result
