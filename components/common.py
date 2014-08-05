# -*- coding: utf-8 -*-

from __future__ import print_function, unicode_literals
import tornado.web
import tornado.gen
import simplejson as json
from datetime import datetime
import bson
import traceback
import os
from multiprocessing import Process
import pymongo
import hashlib
from tornado import gen
from simplejson import JSONEncoder
from threading import Thread


class CallbackThread(Thread):
    def __init__(self, *args, **kwargs):
        self.callback = kwargs.get("callback")
        super(CallbackThread, self).__init__(*args, **kwargs)

    def run(self, *args, **kwargs):
        super(CallbackThread, self).run(*args, **kwargs)
        if self.callback \
            and type(self.callback) == tuple \
            and len(self.callback) == 3 \
            and hasattr(self.callback[0], '__call__') \
            and type(self.callback[1]) == list \
            and type(self.callback[2]) == dict:
            self.callback[0](*self.callback[1], **self.callback[2])


class ThreadPool(object):
    def __init__(self, size):
        super(ThreadPool, self).__init__()
        self.size = size
        self.working = []
        self.queue = []

    def add_thread(self, thread):
        if len(self.working) <= self.size:
            self.working.append(thread)
            thread.callback = (self.thread_finished, [thread], {})
            thread.daemon = True
            thread.start()
        else:
            self.queue.append(thread)

    def thread_finished(self, thread):
        self.working.remove(thread)

        if len(self.queue) > 0:
            thr = self.queue.pop()
            self.working.append(thr)
            thr.start()


def hashfile(afile, blocksize=65536):
    hasher = hashlib.md5()
    buf = afile.read(blocksize)
    while len(buf) > 0:
        hasher.update(buf)
        buf = afile.read(blocksize)
    return hasher.hexdigest()


def get_connection(host, port, user, password, replica, auth=True):
    if not replica:
        con = pymongo.MongoClient(host, port)
    else:
        con = pymongo.MongoReplicaSetClient(host, port, replicaSet=replica)

    if auth:
        con.admin.authenticate(user, password)
    return con


def get_settings_connection(settings, auth=True):
    return get_connection(
        settings.get("host", "127.0.0.1"),
        settings.get("port", 27017),
        settings.get("user", "admin"),
        settings.get("pass", "password"),
        settings.get("replica", None),
        auth=auth
    )


def get_default_database(settings):
    connection = get_settings_connection(settings)
    return connection[settings.get("database", "trunk")]


def authenticate_user(settings, user, password):
    connection = get_settings_connection(settings, auth=False)
    try:
        connection.admin.authenticate(user, password)
        return True
    except pymongo.errors.OperationFailure:
        return False


def run_parallel(fns):
    proc = []
    for fn in fns:
        p = Process(target=fn[0], args=fn[1] or {})
        p.start()
        proc.append(p)
    for p in proc:
        p.join()


class LogicError(Exception):
    pass


class CustomEncoder(JSONEncoder):
    def default(self, obj):
        if type(obj) == datetime:
            return obj.isoformat()
        elif type(obj) == bson.objectid.ObjectId:
            return str(obj)
        else:
            return JSONEncoder.default(self, obj)


class TransparentListener(tornado.web.RequestHandler):
    def get_current_user(self):
        return self.get_secure_cookie("user")

    def get(self, page):
        # Вот тут выдаются страницы
        # Все те, что не статика
        # Потому что мне так велел велоцираптор иисус
        log_message("Page request: {0}".format(page))
        try:
            response = self.application.process_page(
                page,
                self.get_current_user()
            )
            with open(os.path.join(self.application.settings["REALPATH"],
                      response), 'r') as page_file:
                self.write(page_file.read())
            self.finish()
        except Exception as e:
            if e.message == 401:
                self.redirect('/login', permanent=True)
            elif e.message == 404:
                self.redirect('/', permanent=True)

    @tornado.web.asynchronous
    @gen.engine
    def post(self, stuff):
        # Вот тут обрабатывается API
        # Строго через POST
        # Потому что мне так велел летающий макаронный монстр с фрикадельками
        try:
            message = json.loads(self.request.body)
            log_message("API request: {}".format(message.get("function", None)))
        except ValueError:
            self.finish(json.dumps(
                {
                    "result": "failure",
                    "message": "Failed to decode message",
                    "details": traceback.format_exc()
                }, cls=CustomEncoder))
            return

        try:
            # TODO: валидацию понадежнее
            message_secret = message.get("secret")
            response = yield gen.Task(self.application.process_message, **{
                "message": message,
                "user": self.get_current_user(),
                "inner": self.application.settings["secret"] == message_secret,
                "handler": self
            })
        except TypeError as arg:
            response = {
                "result": "failure",
                "message": "Missing argument: {}".format(arg.message)
            }
        except LogicError as arg:
            response = {
                "result": "failure",
                "message": "{0}".format(arg.message)
            }
        except Warning as arg:
            response = {
                "result": "warning",
                "message": "{0}".format(arg.message)
            }
        except Exception:
            response = {
                "result": "failure",
                "message": "Internal server error",
                "details": traceback.format_exc()
            }
        self.set_header("Content-Type", "application/json")
        self.finish(json.dumps(response, cls=CustomEncoder))


def log_message(message, component="Forest", end="\n"):
    print("[{0}][{1}]{2}".format(datetime.now(), component, message), end=end)
