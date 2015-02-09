#!/usr/bin/env python2
# coding=utf-8

from __future__ import unicode_literals, print_function
import sys
from bson import json_util
import cmd

from tornado.httpclient import AsyncHTTPClient
from tornado.ioloop import IOLoop
from tornado.gen import coroutine, Return
import simplejson as json


def asyncloop(f):
    def wraps():
        loop = IOLoop.instance()
        loop.clear_instance()
        try:
            loop.run_sync(coroutine(f))
        except KeyboardInterrupt:
            loop.stop()

    wraps()


@coroutine
def async_client_wrapper(*args, **kwargs):
    http_client = AsyncHTTPClient()
    try:
        res = yield http_client.fetch(*args, **kwargs)
        res = res.body
    except:
        res = None
    raise Return(res)


class ShellTool(cmd.Cmd):

    def __init__(self, host=None, token=None, *args, **kwargs):
        cmd.Cmd.__init__(self, *args, **kwargs)
        self.leaf_name = None
        self.set_prompt()
        self.leaves = []
        self.branches = []
        self.species = []
        self.token = token or ""
        self.do_set_host(host or "127.0.0.1:1234")

    def set_prompt(self, leaf=None):
        self.prompt = "[Forest{}] ".format(": {}".format(leaf) if leaf else "")

    def do_set_host(self, host):
        self.host = host

        @asyncloop
        def async_request_leaves():
            print("Preloading leaves... ", end="")
            try:
                leaves = yield async_client_wrapper(
                    "http://{}/api/druid/leaf".format(self.host),
                    method="GET",
                    request_timeout=1,
                    headers={"Token": self.token}
                )
                self.leaves = json.loads(leaves)
                print("done, {} elements".format(len(self.leaves)))
            except Exception as e:
                print("Failed: {}".format(e))

        @asyncloop
        def async_request_branches():
            print("Preloading branches... ", end="")
            try:
                branches = yield async_client_wrapper(
                    "http://{}/api/druid/branch".format(self.host),
                    method="GET",
                    headers={"Token": self.token}
                )

                self.branches = json.loads(branches)
                print("done, {} elements".format(len(self.branches)))
            except:
                print("failed")

        @asyncloop
        def async_request_species():
            print("Preloading species... ", end="")
            try:
                branches = yield async_client_wrapper(
                    "http://{}/api/druid/species".format(self.host),
                    method="GET",
                    headers={"Token": self.token}
                )

                self.species = json.loads(branches, object_hook=json_util.object_hook)
                print("done, {} elements".format(len(self.species)))
            except:
                print("failed")

    def do_exit(self):
        sys.exit(0)

    def do_use(self, leaf_name):
        if not leaf_name:
            print("Leaf name required")
            return
        self.leaf_name = leaf_name
        self.set_prompt(leaf_name)

    def complete_use(self, text, line, begidx, endidx):
        if not text:
            completions = self.leaves[:]
        else:
            completions = [
                f for f in self.leaves if f.startswith(text)
            ]
        return completions

    def do_stop_leaf(self, leaf_name=None):
        leaf_name = leaf_name or self.leaf_name

        @asyncloop
        def async_request():
            yield async_client_wrapper(
                "http://{}/api/druid/leaf/{}".format(self.host, leaf_name),
                method="PATCH",
                streaming_callback=print,
                headers={"Interactive": "True", "Token": self.token},
                request_timeout=0,
                body=json.dumps({"active": False})
            )

    def do_start_leaf(self, leaf_name=None):
        leaf_name = leaf_name or self.leaf_name

        @asyncloop
        def async_request():
            yield async_client_wrapper(
                "http://{}/api/druid/leaf/{}".format(self.host, leaf_name),
                method="PATCH",
                streaming_callback=print,
                headers={"Interactive": "True", "Token": self.token},
                request_timeout=0,
                body=json.dumps({"active": True})
            )

    def do_watch(self, *args):
        if not self.leaf_name:
            print("Setting leaf name is required")
            return

        def parse_response(data):
            try:
                data = json.loads(data, object_hook=json_util.object_hook)
                if data["log_type"] == "leaf.event":
                    print("[{time}] {method} - {uri}".format(**data))
                elif data["log_type"] == "leaf.stdout_stderr":
                    print("[{time}] {raw}".format(**data))
            except Exception as e:
                print(e)

        @asyncloop
        def async_request():
            yield async_client_wrapper(
                "http://{}/api/druid/logs/{}".format(self.host, self.leaf_name),
                method="GET",
                streaming_callback=parse_response,
                headers={"Interactive": "True", "Token": self.token},
                request_timeout=0
            )

    def do_info(self, leaf_name=None):
        leaf_name = leaf_name or self.leaf_name

        if not leaf_name:
            print("Setting leaf name is required")
            return

        def print_dict(data, ident=0):
            for key, value in data.items():
                if type(value) == dict:
                    print("{}{}:".format(" " * ident, key))
                    print_dict(value, ident+2)
                else:
                    print("{}{}: {}".format(" " * ident, key, value))

        @asyncloop
        def async_request():
            leaf_data = yield async_client_wrapper(
                "http://{}/api/druid/leaf/{}".format(self.host, leaf_name),
                method="GET",
                headers={"Token": self.token}
            )
            print_dict(json.loads(leaf_data, object_hook=json_util.object_hook))

    def do_status(self, leaf_name=None):
        leaf_name = leaf_name or self.leaf_name

        if not leaf_name:
            print("Setting leaf name is required")
            return

        def print_dict(data, ident=0):
            for key, value in data.items():
                if type(value) == dict:
                    print("{}{}:".format(" " * ident, key))
                    print_dict(value, ident+2)
                else:
                    print("{}{}: {}".format(" " * ident, key, value))

        @asyncloop
        def async_request():
            leaf_data = yield async_client_wrapper(
                "http://{}/api/druid/leaf/{}/status".format(self.host, leaf_name),
                method="GET",
                headers={"Token": self.token}
            )
            print_dict(json.loads(leaf_data, object_hook=json_util.object_hook))

    def do_check_branch(self, branch):
        if not branch:
            print("Specify branch")
            return

        @asyncloop
        def async_request():
            yield async_client_wrapper(
                "http://{}/api/druid/branch/{}".format(self.host, branch),
                method="PUT",
                streaming_callback=print,
                headers={"Interactive": "True", "Token": self.token},
                request_timeout=0,
                body=""
            )

    def complete_check_branch(self, text, line, begidx, endidx):
        if not text:
            completions = self.branches[:]
        else:
            completions = [
                f for f in self.branches if f.startswith(text)
            ]
        return completions

    def do_update_species(self, species):
        species = next(x for x in self.species if x["name"] == species)
        print(species)

        @asyncloop
        def async_request():
            yield async_client_wrapper(
                "http://{}/api/druid/species/{}".format(self.host, species["_id"]),
                method="PATCH",
                headers={"Interactive": "True", "Token": self.token},
                body=""
            )

    def complete_update_species(self, text, line, begidx, endidx):
        if not text:
            completions = [x["name"] for x in self.species]
        else:
            completions = [
                f["name"] for f in self.species if f["name"].startswith(text)
            ]
        return completions

    def do_create_leaf(self, args):
        leaf_name, leaf_type, leaf_address = args.split()
        if not all([leaf_name, leaf_type, leaf_address]):
            print("Specify all args")
            return

        @asyncloop
        def async_request():
            yield async_client_wrapper(
                "http://{}/api/druid/leaf".format(self.host),
                method="POST",
                streaming_callback=print,
                headers={"Interactive": "True", "Token": self.token},
                request_timeout=0,
                body=json.dumps({
                    "name": leaf_name,
                    "type": leaf_type,
                    "address": leaf_address
                })
            )

    def do_set_token(self, token):
        self.token = token

    def do_EOF(self, line):
        print()
        return True


if __name__ == '__main__':
    ShellTool().cmdloop()
