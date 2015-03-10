#!/usr/bin/env python2
# coding=utf-8

from __future__ import unicode_literals, print_function
import socket
import os


# pylint: disable=W0613


def generate_config(config_file):
    config = {
        "base": {}
    }
    print("Setting up base Forest configuration")

    base_host = socket.gethostbyname(socket.gethostname())
    config["base"]["host"] = input("Listen address: [{}]".format(base_host)) or base_host
    config["base"]["port"] = input("Listen port: [1234]") or 1234

    base_root = os.path.join(os.path.expanduser("~"), ".forest")
    config["base"]["root"] = input("Forest work directory root: [{}]".format(base_root)) or base_root

    if not os.path.exists(config["base"]["root"]):
        print("Creating Forest root at {}".format(config["base"]["root"]))
        os.makedirs(config["base"]["root"])


if __name__ == '__main__':
    path = input("Specify configuration file path")
    with open(path, "w") as config:
        generate_config(config)
