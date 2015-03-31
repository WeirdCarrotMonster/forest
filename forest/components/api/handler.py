# coding=utf-8

from __future__ import unicode_literals, print_function

from tornado import web


class Handler(web.RequestHandler):

    def __init__(self, application, request, **kwargs):
        super(Handler, self).__init__(application, request, **kwargs)
        self.user = self.get_secure_cookie("user")
        self.closed = False

    def on_connection_close(self):
        self.closed = True
        super(Handler, self).on_connection_close()
