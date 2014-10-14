#coding=utf-8

from __future__ import unicode_literals
from urlparse import parse_qs

from tornado import gen

from components.api.handler import Handler


class Login(Handler):
    @gen.coroutine
    def get(self):
        if self.user:
            self.redirect("/")
        else:
            self.finish(self.application.loader.load("login.html").generate())

    @gen.coroutine
    def post(self):
        data = parse_qs(self.request.body)
        try:
            username = data.get("username")[0]
            password = data.get("password")[0]
        except:
            username = None
            password = None

        if not all([username, password]):
            self.finish(self.application.loader.load("login.html").generate())

        user = yield self.application.authenticate_user(username, password)

        if user:
            self.set_secure_cookie("user", user.get("username"))
            self.redirect("/")
        else:
            self.finish(self.application.loader.load("login.html").generate())


class Index(Handler):
    @gen.coroutine
    def get(self, url):
        if not self.user:
            self.redirect("/login")
        else:
            self.finish(self.application.loader.load("dashboard.html").generate())