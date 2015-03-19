# coding=utf-8

from pymongo.errors import AutoReconnect
from tornado.web import HTTPError

from forest.components.common import log_message


def login_required(fn):
    def wrapped(self, *args, **kwargs):
        if not self.user:
            raise HTTPError(403)
        return fn(self, *args, **kwargs)
    return wrapped


def ignore_autoreconnect(fn):
    def wrapped(*args, **kwargs):
        try:
            return fn(*args, **kwargs)
        except AutoReconnect:
            log_message("MongoDB connection failed, will retry on next iteration...")
    return wrapped
