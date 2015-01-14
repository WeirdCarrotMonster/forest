# coding=utf-8

from __future__ import unicode_literals, print_function

from tornado import web


class Handler(web.RequestHandler):
    def __init__(self, application, request, **kwargs):
        super(Handler, self).__init__(application, request, **kwargs)
        self.user = self.get_secure_cookie("user")
        self.interactive = self.request.headers.get("Interactive", "False") == "True"

    def note(self, note):
        if self.interactive:
            self.write(note)
            self.flush()
