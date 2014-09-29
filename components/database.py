# -*- coding: utf-8 -*-

import motor
import pymongo


def get_connection_async(host, port, user, password, replica):
    if not replica:
        con = motor.MotorClient("mongodb://{user}:{password}@{host}:{port}/admin".format(**locals()))
    else:
        con = motor.MotorReplicaSetClient(
            "mongodb://{user}:{password}@{host}:{port}/admin".format(**locals()),
            replicaSet=replica)
    return con


def get_settings_connection_async(settings):
    return get_connection_async(
        settings.get("host", "127.0.0.1"),
        settings.get("port", 27017),
        settings.get("user", "admin"),
        settings.get("pass", "password"),
        settings.get("replica", None)
    )


def get_connection(host, port, user, password, replica):
    if not replica:
        con = pymongo.MongoClient(
            "mongodb://{user}:{password}@{host}:{port}/admin".format(**locals()))
    else:
        con = pymongo.MongoReplicaSetClient(
            "mongodb://{user}:{password}@{host}:{port}/admin".format(**locals()),
            replicaSet=replica)
    return con


def get_settings_connection(settings):
    return get_connection(
        settings.get("host", "127.0.0.1"),
        settings.get("port", 27017),
        settings.get("user", "admin"),
        settings.get("pass", "password"),
        settings.get("replica", None)
    )


def get_default_database(settings, async=False):
    if async:
        connection = get_settings_connection_async(settings)
    else:
        connection = get_settings_connection(settings)
    return connection[settings.get("database", "trunk")]


def authenticate_user(settings, user, password):
    connection = get_settings_connection(settings)
    try:
        connection.admin.authenticate(user, password)
        return True
    except pymongo.errors.OperationFailure:
        return False