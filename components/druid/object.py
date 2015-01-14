#coding=utf-8


class Druid(object):
    def __init__(self, trunk, settings):
        self.trunk = trunk
        self.__air__ = settings.get("air", [])
        self.__roots__ = settings.get("roots", [])
        self.__branch__ = settings.get("branch", [])

    @property
    def air(self):
        return self.__air__

    @property
    def roots(self):
        return self.__roots__

    @property
    def branch(self):
        return self.__branch__
