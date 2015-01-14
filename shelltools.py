#!/usr/bin/env python2
#coding=utf-8

from __future__ import unicode_literals, print_function
from tornado.httpclient import AsyncHTTPClient
from tornado.ioloop import IOLoop
import sys
import simplejson as json


def handle_request(data):
    print(data)


def done(data):
    sys.exit(0)


def send_request(resource, reqtype, data):
    http_client = AsyncHTTPClient()
    http_client.fetch(
        "http://127.0.0.1:1234/api/{}".format(resource),
        body=json.dumps(data),
        method=reqtype,
        streaming_callback=handle_request,
        callback=done,
        headers={"Interactive": "True"}
    )


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

    if len(params) < len(command[2]):
        print("Wrong arguments count: expected {}".format(", ".join(command[2])))
        sys.exit(0)

    required_params = params[:len(command[2])]
    data = {}
    for k, v in zip(command[2], required_params):
        data[k] = v
    send_request(command[0], command[1], data)

commands = {
    "create_leaf": ("druid/leaf", "POST", ["name", "type", "address"])
}


loop = IOLoop.instance()

parsecmd()

loop.start()
