#!/usr/bin/env python2
#coding=utf-8

from __future__ import unicode_literals, print_function
from tornado.httpclient import AsyncHTTPClient
from tornado.ioloop import IOLoop
from tornado.gen import coroutine
import sys
import simplejson as json
from bson import json_util


def parse_response(data):
    try:
        data = json.loads(data, object_hook=json_util.object_hook)
        if data["log_type"] == "leaf.event":
            print("[{added}] {method} - {uri}".format(**data))
        elif data["log_type"] == "leaf.stdout_stderr":
            print("[{added}] {raw}".format(**data))
    except:
        print(data)


@coroutine
def send_request(resource, method, data):
    http_client = AsyncHTTPClient()
    if method in ("GET", "DELETE"):
        yield http_client.fetch(
            "http://127.0.0.1:1234/api/{}".format(resource.format(**data)),
            method=method,
            streaming_callback=parse_response,
            headers={"Interactive": "True"},
            request_timeout=0
        )
    else:
        yield http_client.fetch(
            "http://127.0.0.1:1234/api/{}".format(resource.format(**data)),
            body=json.dumps(data),
            method=method,
            streaming_callback=print,
            headers={"Interactive": "True"},
            request_timeout=0
        )
    sys.exit(0)


@coroutine
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

    yield send_request(command["resource"], command["method"], data)

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
    },
    "check_branch": {
        "resource": "druid/branch/{name}",
        "method": "PUT",
        "args": ["name"],
        "update": {"active": True}
    },
    "watch_logs": {
        "resource": "druid/logs/{name}",
        "method": "GET",
        "args": ["name"]
    },
}


loop = IOLoop.instance()
parsecmd()

loop.start()
