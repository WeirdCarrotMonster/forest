# -*- coding: utf-8 -*-
import subprocess
import tornado.web
import tornado.httpclient
from components.common import get_connection


class Air(tornado.web.Application):

    def __init__(self, settings_dict, **settings):
        super(Air, self).__init__(**settings)
        self.settings = settings_dict

        self.functions = {
            "update_state": self.update_state,
            "status_report": self.status_report
        }

    def update_state(self, message):
        self.reload_proxy()

    def process_message(self, message):
        function = message.get('function', None)

        if not function in self.functions:
            return {
                "result": "failure",
                "message": "No function or unknown one called"
            }

        return self.functions[function](message)

    def status_report(self, message):
        return {
            "result": "success",
            "message": "Working well",
            "role": "air"
        }

    def reload_proxy(self):
        cmd = self.settings["proxy_restart_command"].split()
        subprocess.Popen(cmd, shell=False)


def get_leaves_proxy(settings):
    client = get_connection(
        settings["settings"]["mongo_host"],
        settings["settings"]["mongo_port"],
        "admin",
        "password"
    )

    leaves = client.trunk.leaves.find({
        "active": True
    })
    for leaf in leaves:
        branch = client.trunk.branches.find_one({"name": leaf["branch"]})
        if not branch:
            continue
        address = leaf["address"]
        host = branch["host"]
        port = leaf["port"]
        conf = '''
$HTTP["host"] == "''' + address + '''" {
    fastcgi.server = ("/" => ((
        "host" => "''' + host + '''",
        "port" => ''' + str(port) + ''',
        "check-local" => "disable",
        "disable-time" => 1,
        "fix-root-scriptname" => "enable"
    )))
}
        '''
        print(conf)
