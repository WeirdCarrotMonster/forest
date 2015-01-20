#!/usr/bin/env python2
# coding=utf-8

from __future__ import unicode_literals, print_function
from tornado.httpclient import AsyncHTTPClient
from tornado.ioloop import IOLoop
from tornado.gen import coroutine, Return
import sys
import simplejson as json
from bson import json_util
import cmd


def asyncloop(f):
    def wraps(*args, **kwargs):
        loop = IOLoop.instance()

        try:
            coroutine(f)(loop, *args, **kwargs)
        except Exception, e:
            print(e)

        try:
            loop.start()
        except:
            print("", end="\r")
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
    def __init__(self, *args, **kwargs):
        self.leaf_name = None
        cmd.Cmd.__init__(self, *args, **kwargs)
        self.set_prompt()
        self.leaves = []
        self.branches = []

        @asyncloop
        def async_request_leaves(loop):
            print("Preloading leaves...", end="")
            leaves = yield async_client_wrapper(
                "http://127.0.0.1:1234/api/druid/leaf",
                method="GET"
            )

            self.leaves = json.loads(leaves)
            print("done, {} elements".format(len(self.leaves)))
            loop.stop()

        @asyncloop
        def async_request_branches(loop):
            print("Preloading branches...", end="")
            branches = yield async_client_wrapper(
                "http://127.0.0.1:1234/api/druid/branch",
                method="GET"
            )

            self.branches = json.loads(branches)
            print("done, {} elements".format(len(self.branches)))
            loop.stop()

    def set_prompt(self, leaf=None):
        self.prompt = "[Forest{}] ".format(": {}".format(leaf) if leaf else "")

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
        def async_request(loop):
            yield async_client_wrapper(
                "http://127.0.0.1:1234/api/druid/leaf/{}".format(leaf_name),
                method="PATCH",
                streaming_callback=print,
                headers={"Interactive": "True"},
                request_timeout=0,
                body=json.dumps({"active": False})
            )
            loop.stop()

    def do_start_leaf(self, leaf_name=None):
        leaf_name = leaf_name or self.leaf_name

        @asyncloop
        def async_request(loop):
            yield async_client_wrapper(
                "http://127.0.0.1:1234/api/druid/leaf/{}".format(leaf_name),
                method="PATCH",
                streaming_callback=print,
                headers={"Interactive": "True"},
                request_timeout=0,
                body=json.dumps({"active": True})
            )
            loop.stop()

    def do_watch(self, *args):
        if not self.leaf_name:
            print("Setting leaf name is required")
            return

        def parse_response(data):
            try:
                data = json.loads(data, object_hook=json_util.object_hook)
                if data["log_type"] == "leaf.event":
                    print("[{added}] {method} - {uri}".format(**data))
                elif data["log_type"] == "leaf.stdout_stderr":
                    print("[{added}] {raw}".format(**data))
            except:
                print(data)

        @asyncloop
        def async_request(loop):
            yield async_client_wrapper(
                "http://127.0.0.1:1234/api/druid/logs/{}".format(self.leaf_name),
                method="GET",
                streaming_callback=parse_response,
                headers={"Interactive": "True"},
                request_timeout=0
            )
            loop.stop()

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
        def async_request(loop):
            leaf_data = yield async_client_wrapper(
                "http://127.0.0.1:1234/api/druid/leaf/{}".format(leaf_name),
                method="GET"
            )
            print_dict(json.loads(leaf_data, object_hook=json_util.object_hook))
            loop.stop()

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
        def async_request(loop):
            leaf_data = yield async_client_wrapper(
                "http://127.0.0.1:1234/api/druid/leaf/{}/status".format(leaf_name),
                method="GET"
            )
            print_dict(json.loads(leaf_data, object_hook=json_util.object_hook))
            loop.stop()

    def do_check_branch(self, branch):
        if not branch:
            print("Specify branch")
            return

        @asyncloop
        def async_request(loop):
            yield async_client_wrapper(
                "http://127.0.0.1:1234/api/druid/branch/{}".format(branch),
                method="PUT",
                streaming_callback=print,
                headers={"Interactive": "True"},
                request_timeout=0,
                body=""
            )
            loop.stop()

    def complete_check_branch(self, text, line, begidx, endidx):
        if not text:
            completions = self.branches[:]
        else:
            completions = [
                f for f in self.branches if f.startswith(text)
            ]
        return completions

    def do_create_leaf(self, args):
        leaf_name, leaf_type, leaf_address = args.split()
        if not all([leaf_name, leaf_type, leaf_address]):
            print("Specify all args")
            return

        @asyncloop
        def async_request(loop):
            yield async_client_wrapper(
                "http://127.0.0.1:1234/api/druid/leaf",
                method="POST",
                streaming_callback=print,
                headers={"Interactive": "True"},
                request_timeout=0,
                body=json.dumps({
                    "name": leaf_name,
                    "type": leaf_type,
                    "address": leaf_address
                })
            )
            loop.stop()

    def do_EOF(self, line):
        print()
        return True


if __name__ == '__main__':
    ShellTool().cmdloop()
