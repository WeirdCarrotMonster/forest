# coding=utf-8
"""Описывает широкоиспользуемые функции по работе с компонентами."""

from __future__ import unicode_literals, print_function
from tornado.gen import coroutine, Return
from forest.components.common import send_request


@coroutine
def branch_prepare_species(branch, species):
    """Проверяет и подготоваливает указанный вид листа на указанной ветви.

    :param branch: Ветвь
    :type branch: dict
    :param species: Тип листа
    :type species: dict
    """
    response, code = yield send_request(
        branch,
        "branch/species/{}".format(species["_id"]),
        "GET"
    )

    # TODO: проверять не только код, но и дату модификации вида
    if code == 404:
        response, code = yield send_request(
            branch,
            "branch/species",
            "POST",
            species
        )

    raise Return((response, code))


@coroutine
def branch_start_leaf(branch, leaf):
    """Запускает лист на указанной ветви.

    :param branch: Ветвь
    :type branch: dict
    :param leaf: Запускаемый лист
    :type leaf: dict
    """
    response = yield send_request(branch, "branch/leaf", "POST", leaf)
    raise Return(response)


@coroutine
def branch_stop_leaf(branch, leaf):
    """Останавливает лист на указанной ветви.

    :param branch: Ветвь
    :type branch: dict
    :param leaf: Останавливаемый лист
    :type leaf: dict
    """
    response = yield send_request(branch, "branch/leaf/{}".format(str(leaf["_id"])), "DELETE")
    raise Return(response)


@coroutine
def air_enable_host(air, host):
    """Разрешает указанный хост на прокси-сервере.

    :param air: Прокси-сервер
    :type air: dict
    :param host: Добавляемый в список разрешенных хост
    :type host: str
    """
    response = yield send_request(air, "air/hosts", "POST", {"host": host})
    raise Return(response)


def full_leaf_info(leaf, air_servers, species):
    """Возвращает полный словарь настроек листа.

    :param leaf: Базовый словарь настроек листа
    :type leaf: dict
    :param air_servers: Список прокси-серверов
    :type air_servers: list
    :param species: Вид листа
    :type species: dict
    """
    leaf["fastrouters"] = ["{host}:{fastrouter}".format(**a) for a in air_servers]
    leaf["uwsgi_mules"] = species.get("uwsgi_mules", [])
    leaf["uwsgi_triggers"] = species.get("triggers", {})

    return leaf
