#!/usr/bin/env python2
#coding=utf-8

from __future__ import unicode_literals, print_function
from tornado.httpclient import AsyncHTTPClient
from tornado.ioloop import IOLoop
from tornado.gen import coroutine
import sys
import simplejson as json


@coroutine
def send_request(resource, method, data):
    http_client = AsyncHTTPClient()
    yield http_client.fetch(
        "http://127.0.0.1:1234/api/{}".format(resource.format(**data)),
        body=json.dumps(data),
        method=method,
        streaming_callback=print,
        headers={"Interactive": "True"}
    )
    sys.exit(0)


def parsecmd():
    if len(sys.argv) < 2:
        print("Wrong number of arguments specified")
        sys.exit(0)
    cmd = sys.argv[1]
    params = sys.argv[2:]

    command = commands[cmd]

    if cmd not in commands:
        print("Unknown command")
        sys.exit(0)

    if len(params) < len(command["args"]):
        print("Wrong arguments count: expected {}".format(", ".join(command["args"])))
        sys.exit(0)

    required_params = params[:len(command["args"])]
    data = {}
    for k, v in zip(command["args"], required_params):
        data[k] = v

    data.update(command.get("update", {}))

    send_request(command["resource"], command["method"], data)

commands = {
    "create_leaf": {
        "resource": "druid/leaf",
        "method": "POST",
        "args": ["name", "type", "address"]
    },
    "stop_leaf": {
        "resource": "druid/leaf/{name}",
        "method": "PATCH",
        "args": ["name"],
        "update": {"active": False}
    },
    "start_leaf": {
        "resource": "druid/leaf/{name}",
        "method": "PATCH",
        "args": ["name"],
        "update": {"active": True}
    }
}


loop = IOLoop.instance()

parsecmd()

loop.start()
