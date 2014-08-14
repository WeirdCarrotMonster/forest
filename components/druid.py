# -*- coding: utf-8 -*-
"""
Модуль реализует класс веб-интерфейса, отвечающего за обработку
запросов API и прочую внутреннюю логику, связанную с управлением
лесом и выполнением запросов к другим компонентам.
"""
import pymongo
from components.common import LogicError
from components.database import get_default_database
from bson.objectid import ObjectId


class Druid():
    def __init__(self, settings, trunk):
        self.settings = settings
        self.trunk = trunk
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
            # Работа с ветвями
            "get_branches": self.get_branches,
            "get_branch_logs": self.get_branch_logs
        }

    def __get_common_settings(self):
        trunk = get_default_database(self.settings)
        branches = trunk.components.find({"roles.branch": {"$exists": True}})

        return {
            "address": {
                "type": "list",
                "elements": "string",
                "verbose": "Адреса"
            },
            "branch": {
                "type": "checkbox_list",
                "values": [{
                    "verbose": branch["name"],
                    "value": branch["_id"]
                } for branch in branches],
                "verbose": "Ветви"
            }
        }

    def __parse_common_settings(self, settings):
        return {
            "branch": [ObjectId(adr) for adr in settings.get("branch", [])],
            "address": settings.get("address", [])
        }

    def get_default_settings(self, specie_id, **kwargs):
        trunk = get_default_database(self.settings)

        leaf_type = trunk.species.find_one({"_id": ObjectId(specie_id)})

        return {
            "result": "success",
            "settings": {
                "common": self.__get_common_settings(),
                "custom": leaf_type.get("settings", {})
            }
        }

    def get_leaf_settings(self, leaf_id, **kwargs):
        trunk = get_default_database(self.settings)
        leaves = trunk.leaves
        species = trunk.species

        leaf = leaves.find_one({"_id": ObjectId(leaf_id)})
        leaf_type = species.find_one({"_id": leaf["type"]})

        return {
            "result": "success",
            "settings": {
                "custom": leaf.get("settings", {}),
                "common": {
                    "address": leaf.get("address"),
                    "branch": leaf.get("branch")
                },
                "template": {
                    "common": self.__get_common_settings(),
                    "custom": leaf_type["settings"]
                }
            }
        }

    def set_leaf_settings(self, leaf_id, settings, **kwargs):
        trunk = get_default_database(self.settings)
        leaves = trunk.leaves

        settings["common"] = self.__parse_common_settings(settings["common"])

        # TODO: переписать с итерацией по дефолтным настройкам
        leaves.update(
            {"_id": ObjectId(leaf_id)},
            {
                "$set": {
                    "settings": settings["custom"],
                    "address": settings["common"]["address"],
                    "branch": settings["common"]["branch"]
                }
            }
        )

        self.update_branches()
        self.update_air()

        return {
            "result": "success"
        }

    def get_branch_logs(self, branch_id, offset=0, limit=200, **kwargs):
        trunk = get_default_database(self.settings)

        logs_raw = trunk.logs.find({
            "component_type": "branch",
            "component": ObjectId(branch_id),
            "log_type": {"$ne": "leaf.event"}
        }).sort("added", -1)[offset:offset+limit]

        return {
            "result": "success",
            "logs": [l for l in logs_raw]
        }

    def get_branches(self, **kwargs):
        # TODO: переписать с аггрегацией
        trunk = get_default_database(self.settings)

        branches = []
        components = trunk.components
        for branch in components.find({"roles.branch": {"$exists": True}}):
            branches.append({
                "name": branch["name"],
                "id": branch["_id"]
            })

        return {
            "result": "success",
            "branches": branches
        }

    def update_air(self):
        trunk = get_default_database(self.settings)
        components = trunk.components
        for component in components.find({"roles.air": {"$exists": True}}):
            self.trunk.send_message(component, {"function": "air.update_state"})

    def update_branches(self):
        trunk = get_default_database(self.settings)
        components = trunk.components
        for branch in components.find({"roles.branch": {"$exists": True}}):
            self.trunk.send_message(branch, {"function": "branch.update_state"})

    def update_roots(self):
        trunk = get_default_database(self.settings)
        components = trunk.components
        root = components.find_one({"roles.roots": {"$exists": True}})
        self.trunk.send_message(root, {"function": "roots.update_state"})

    def update_repo(self, type, **kwargs):
        pass

    def create_leaf(self, name, leaf_type, settings, desc="", **kwargs):
        trunk = get_default_database(self.settings)
        leaves = trunk.leaves

        if leaves.find_one({"name": name}):
            raise LogicError("Leaf with name '{0}' \
                              already exists".format(name))

        # TODO: проверка адреса

        leaf = leaves.insert({
            "name": name,
            "desc": desc,
            "type": ObjectId(leaf_type),
            "active": True,
            "address": settings["common"]["urls"],
            "branch": settings["common"]["branch"],
            "settings": settings["custom"]
        })

        self.update_roots()
        self.update_branches()
        self.update_air()

        return {
            "result": "success",
            "id": leaf.get("_id")
        }

    def get_species(self, **kwargs):
        trunk = get_default_database(self.settings)

        species = [
            (specie["name"], specie["_id"]) for specie in trunk.species.find()
        ]

        return {
            "result": "success",
            "species": species
        }

    def toggle_leaf(self, leaf_id, **kwargs):
        trunk = get_default_database(self.settings)
        leaves = trunk.leaves

        leaf = leaves.find_one({"_id": ObjectId(leaf_id)})

        leaves.update(
            {"_id": ObjectId(leaf_id)},
            {
                "$set": {
                    "active": not leaf["active"]
                }
            }
        )

        self.update_branches()
        self.update_air()

        leaf_raw = leaves.find_one({"_id": ObjectId(leaf_id)})
        leaf_response = {
            "id": leaf_raw.get("_id"),
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

    def get_leaf_logs(self, leaf_id, offset=0, limit=200, last=None, **kwargs):
        # Проверяем наличие требуемых аргументов
        trunk = get_default_database(self.settings)

        if last:
            last_log = trunk.logs.find_one({"_id": ObjectId(last)})
            logs_raw = trunk.logs.find({
                "log_source": ObjectId(leaf_id),
                "added": {
                    "$gt": last_log.get("added")
                }
            }).sort("added", -1)
        else:
            logs_raw = trunk.logs.find({"log_source": ObjectId(leaf_id)}).sort("added", -1)[offset:offset+limit]

        return {
            "result": "success",
            "logs": [l for l in logs_raw]
        }

    def get_leaves(self, **kwargs):
        trunk = get_default_database(self.settings)

        leaves = trunk.leaves.find().sort('name', pymongo.ASCENDING)
        # TODO: генерировать список средствами MongoDB
        leaves_list = [
            {
                "id": leaf.get("_id"),
                "name": leaf.get("name"),
                "desc": leaf.get("desc"),
                "urls": leaf.get("address") if type(leaf.get("address")) == list else [leaf.get("address")],
                "type": leaf.get("type"),
                "active": leaf.get("active"),
                "branch": leaf.get("branch") if type(leaf.get("branch")) == list else [leaf.get("branch")]
            } for leaf in leaves
        ]
        return {"result": "success", "leaves": leaves_list}

