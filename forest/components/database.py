# coding=utf-8
"""Модуль описывает функции получения синхронного и асинхронного подключения к базе."""

import motor
import pymongo


# pylint: disable=R0913,W0613


def get_connection_async(
        host="127.0.0.1",
        port=27017,
        database="trunk",
        user="admin",
        password="password",
        replica=None,
        **kwargs
        ):
    """Возвращает асинхронное подключение к базе.

    :param host: Хост, к которому выполняется подключение
    :type host: str
    :param port: Порт базы данных
    :type port: int
    :param user: Имя пользователя базы данных
    :type user: str
    :param password: Пароль пользователя базы данных
    :type password: str
    :param replica: Название replicaSet (при наличии)
    :type replica: str
    :param database: Имя базы данных
    :type database: str
    """
    if not replica:
        con = motor.MotorClient(
            "mongodb://{}:{}@{}:{}/{}".format(
                user, password,
                host, port,
                database
            ))
    else:
        con = motor.MotorReplicaSetClient(
            "mongodb://{}:{}@{}:{}/{}".format(
                user, password,
                host, port,
                database
            ),
            replicaSet=replica,
            connectTimeoutMS=1500,
            socketTimeoutMS=1500
        )
    return con


def get_connection(
        host="127.0.0.1",
        port=27017,
        database="trunk",
        user="admin",
        password="password",
        replica=None,
        **kwargs
        ):
    """Возвращает синхронное подключение к базе.

    :param host: Хост, к которому выполняется подключение
    :type host: str
    :param port: Порт базы данных
    :type port: int
    :param user: Имя пользователя базы данных
    :type user: str
    :param password: Пароль пользователя базы данных
    :type password: str
    :param replica: Название replicaSet (при наличии)
    :type replica: str
    :param database: Имя базы данных
    :type database: str
    """
    if not replica:
        con = pymongo.MongoClient(
            "mongodb://{}:{}@{}:{}/{}".format(
                user, password,
                host, port,
                database
            ))
    else:
        con = pymongo.MongoReplicaSetClient(
            "mongodb://{}:{}@{}:{}/{}".format(
                user, password,
                host, port,
                database
            ),
            replicaSet=replica,
            connectTimeoutMS=1500,
            socketTimeoutMS=1500
        )
    return con
