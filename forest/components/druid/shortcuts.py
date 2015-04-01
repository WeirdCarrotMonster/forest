# coding=utf-8

from __future__ import unicode_literals, print_function
from tornado.gen import coroutine, Return
from forest.components.common import send_request


@coroutine
def branch_prepare_species(branch, species):
    response, code = yield send_request(
        branch,
        "branch/species/{}".format(species["_id"]),
        "GET"
    )

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
    response = yield send_request(branch, "branch/leaf", "POST", leaf)
    raise Return(response)


@coroutine
def branch_stop_leaf(branch, leaf):
    response = yield send_request(branch, "branch/leaf/{}".format(str(leaf["_id"])), "DELETE")
    raise Return(response)


@coroutine
def air_enable_host(air, host):
    response = yield send_request(air, "air/hosts", "POST", {"host": host})
    raise Return(response)


def full_leaf_info(leaf, air_servers, species):
    leaf["fastrouters"] = ["{host}:{fastrouter}".format(**a) for a in air_servers]
    leaf["uwsgi_mules"] = species.get("uwsgi_mules", [])
    leaf["uwsgi_triggers"] = species.get("triggers", {})

    return leaf
