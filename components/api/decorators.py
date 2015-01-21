# coding=utf-8

from __future__ import unicode_literals, print_function
import simplejson as json
from tornado.gen import Return


def token_auth(f):
    def wrapper(self, *args, **kwargs):
        if self.application.secret != self.request.headers.get("Token"):
            self.set_status(403)
            self.finish(json.dumps({
                "result": "error",
                "message": "Not authenticated"
            }))
            raise Return()
        else:
            return f(self, *args, **kwargs)

    return wrapper
