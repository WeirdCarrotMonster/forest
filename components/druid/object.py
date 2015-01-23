# coding=utf-8

from toro import Queue
from collections import defaultdict
from tornado import gen


class Druid(object):

    def __init__(self, trunk, settings):
        self.trunk = trunk
        self.__air__ = settings.get("air", [])
        self.__roots__ = settings.get("roots", [])
        self.__branch__ = settings.get("branch", [])
        self.__log_listeners__ = defaultdict(set)

    def get_listener(self, leaf_id):
        q = Queue()
        self.__log_listeners__[leaf_id].add(q)
        return q

    def remove_listener(self, leaf_id, listener):
        if listener in self.__log_listeners__[leaf_id]:
            self.__log_listeners__[leaf_id].remove(listener)

    @gen.coroutine
    def store_log(self, log):
        yield self.trunk.async_db.logs.insert(log)

    @gen.coroutine
    def propagate_event(self, event):
        leaf = event.get("log_source")

        yield self.store_log(event)

        for l in self.__log_listeners__[leaf]:
            l.put(event)

    @property
    def air(self):
        return self.__air__

    @property
    def roots(self):
        return self.__roots__

    @property
    def branch(self):
        return self.__branch__
