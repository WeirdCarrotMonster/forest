#coding=utf-8
from tornado.web import HTTPError


def login_required(fn):
    def wrapped(self, *args, **kwargs):
        if not self.user:
            raise HTTPError(403)
        return fn(self, *args, **kwargs)
    return wrapped
