# -*- coding: utf-8 -*-

import motor
import pymongo


def get_connection_async(host, port, user, password, replica, database="trunk"):
    if not replica:
        con = motor.MotorClient("mongodb://{user}:{password}@{host}:{port}/{database}".format(**locals()))
    else:
        con = motor.MotorReplicaSetClient(
            "mongodb://{user}:{password}@{host}:{port}/{database}".format(**locals()),
            replicaSet=replica,
            connectTimeoutMS=1500,
            socketTimeoutMS=1500
        )
    return con


def get_settings_connection_async(settings):
    return get_connection_async(
        settings.get("host", "127.0.0.1"),
        settings.get("port", 27017),
        settings.get("user", "admin"),
        settings.get("pass", "password"),
        settings.get("replica", None),
        settings.get("database", "trunk")
    )


def get_connection(host, port, user, password, replica, database="trunk"):
    if not replica:
        con = pymongo.MongoClient(
            "mongodb://{user}:{password}@{host}:{port}/{database}".format(**locals()))
    else:
        con = pymongo.MongoReplicaSetClient(
            "mongodb://{user}:{password}@{host}:{port}/{database}".format(**locals()),
            replicaSet=replica,
            connectTimeoutMS=1500,
            socketTimeoutMS=1500
        )
    return con


def get_settings_connection(settings):
    return get_connection(
        settings.get("host", "127.0.0.1"),
        settings.get("port", 27017),
        settings.get("user", "admin"),
        settings.get("pass", "password"),
        settings.get("replica", None),
        settings.get("database", "trunk")
    )


def get_default_database(settings, async=False):
    if async:
        connection = get_settings_connection_async(settings)
    else:
        connection = get_settings_connection(settings)
    return connection[settings.get("database", "trunk")]
