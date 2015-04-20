#!/usr/bin/env python2
# coding=utf-8

"""Набор утилит для интерактивной командной строки."""

from __future__ import unicode_literals, print_function

from cmd import Cmd

from forest.components.common import dumps, loads
import requests
import simplejson as json
from tornado.gen import coroutine
from tornado.ioloop import IOLoop
from tornado.httpclient import HTTPRequest
from tornado.websocket import websocket_connect


# pylint: disable=W0702,W0612,W0613


def print_dict(data, ident=0):
    """Печатает словарь с несколькими уровнями вложенности.

    :param ident: Отступ вложенности
    :type ident: int
    """
    for key, value in data.items():
        if type(value) == dict:
            print("{}{}:".format(" " * ident, key))
            print_dict(value, ident + 2)
        else:
            print("{}{}: {}".format(" " * ident, key, value))


def print_log(data):
    """Парсит и печатает лог листа.

    :param data: Лог листа
    :type data: dict
    """
    try:
        if data["log_type"] == "leaf.event":
            if "traceback" in data and data["traceback"] != "-":
                print(
                    "[{time}] {status} {method} - {uri} "
                    "[ Traceback id: {traceback} ]".format(**data)
                )
            else:
                print("[{time}] {status} {method} - {uri}".format(**data))
        elif data["log_type"] == "leaf.stdout_stderr":
            print("[{time}] {raw}".format(**data))
    except Exception:
        import traceback
        traceback.print_exc()


class LeafShell(Cmd):

    """Интерактивный shell для работы с листом."""

    def __init__(self, leaf, _id, host, token, *args, **kwargs):
        """Инициализирует shell.

        :param leaf: Имя листа
        :type leaf: str
        :param _id: Идентификатор листа
        :type _id: ObjectId
        :param host: Целевой хост
        :type host: str
        :param token: Ключ аутентификации
        :type token: str
        """
        Cmd.__init__(self, *args, **kwargs)
        self.__leaf__ = leaf
        self.__id__ = _id
        self.host = host
        self.token = token

        self.prompt = "[Leaf '{}'] ".format(leaf)

    def emptyline(self):
        """Обработка пустой строки."""
        pass

    def do_exit(self, *args, **kwargs):
        """Обработка команды exit."""
        return True

    def do_EOF(self, *args, **kwargs):
        """Обработка действия при получении EOF."""
        print()
        return True

    def do_stop_leaf(self, *args, **kwargs):
        """Останавливает лист."""
        r = requests.patch(
            "http://{}/api/druid/leaf/{}".format(self.host, self.__leaf__),
            headers={"Token": self.token},
            data=json.dumps({"active": False})
        )
        print(r.text)

    def do_start_leaf(self, *args, **kwargs):
        """Запускает лист."""
        r = requests.patch(
            "http://{}/api/druid/leaf/{}".format(self.host, self.__leaf__),
            headers={"Token": self.token},
            data=json.dumps({"active": True})
        )
        print(r.text)

    def do_watch(self, *args, **kwargs):
        """Выводит в консоль логи листа в реальном времени."""
        def watch_logs():
            conn = yield websocket_connect(HTTPRequest(
                "ws://{}/api/druid/logs/{}".format(self.host, self.__id__),
                headers={"Token": self.token}
            ))
            while True:
                msg = yield conn.read_message()

                if not msg:
                    break

                print_log(loads(msg))

        loop = IOLoop.instance()
        loop.clear_instance()
        try:
            loop.run_sync(coroutine(watch_logs))
        except KeyboardInterrupt:
            loop.stop()
            print("", end="\r")

    def do_info(self, *args, **kwargs):
        """Выводит информацию о листе."""
        r = requests.get(
            "http://{}/api/druid/leaf/{}".format(self.host, self.__leaf__),
            headers={"Token": self.token}
        )
        print_dict(loads(r.text))

    def do_status(self, *args, **kwargs):
        """Выводит статус листа."""
        r = requests.get(
            "http://{}/api/druid/leaf/{}/status".format(self.host, self.__leaf__),
            headers={"Token": self.token}
        )
        print_dict(loads(r.text))

    def do_find_traceback(self, tb_id):
        """Ищет трейсбек ошибки по его id.

        :param tb_id: id трейсбека
        :type tb_id: str
        """
        r = requests.get(
            "http://{}/api/druid/traceback/{}".format(self.host, tb_id),
            headers={"Token": self.token}
        )
        print(loads(r.text)["traceback"])


class ShellTool(Cmd):

    """Интерактивный shell леса."""

    def __init__(self, host=None, token=None, *args, **kwargs):
        """Инициализирует интерактивный shell.

        :param host: Целевой host
        :type host: str
        :param token: Секретный ключ
        :type token: str
        """
        Cmd.__init__(self, *args, **kwargs)
        self.leaf_name = None
        self.prompt = "[Forest] "
        self.leaves = []
        self.branches = []
        self.species = []
        self.token = token or ""
        self.do_set_host(host or "127.0.0.1:1234")

    def emptyline(self):
        """Обработчик пустой строки."""
        pass

    def do_set_host(self, host):
        """Устанавливает хост брокера и подгружает данные.

        :param host: Хост брокера
        :type host: str
        """
        self.host = host

        print("Preloading leaves... ", end="")
        try:
            r = requests.get(
                "http://{}/api/druid/leaf".format(self.host),
                headers={"Token": self.token}
            )
            self.leaves = loads(r.text)
            print("done, {} elements".format(len(self.leaves)))
        except Exception as e:
            print("Failed: {}".format(e))

        print("Preloading branches... ", end="")
        try:
            r = requests.get(
                "http://{}/api/druid/branch".format(self.host),
                headers={"Token": self.token}
            )
            self.branches = loads(r.text)
            print("done, {} elements".format(len(self.branches)))
        except Exception as e:
            print("Failed: {}".format(e))

        print("Preloading species... ", end="")
        try:
            r = requests.get(
                "http://{}/api/druid/species".format(self.host),
                headers={"Token": self.token}
            )
            self.species = loads(r.text)
            print("done, {} elements".format(len(self.species)))
        except Exception as e:
            print("Failed: {}".format(e))

    def do_exit(self, *args, **kwargs):
        """Обработчик команды выхода."""
        return True

    def do_use(self, leaf_name):
        """Обработчик команды use.

        Запускает LeafShell для листа с именем leaf_name.
        :param leaf_name: Имя используемого листа
        :type leaf_name: str
        """
        if not leaf_name:
            print("Leaf name required")
            return

        try:
            leaf = next(x for x in self.leaves if x["name"] == leaf_name)
        except StopIteration:
            print("Unknown leaf")
            return

        LeafShell(leaf_name, leaf["_id"], self.host, self.token).cmdloop()

    def complete_use(self, text, line, begidx, endidx):
        """Автокомплит для команды use."""
        if not text:
            completions = self.leaves[:]
        else:
            completions = [
                f["name"] for f in self.leaves if f["name"].startswith(text)
            ]
        return completions

    def do_check_branch(self, branch):
        """Обработчик команды check_branch."""
        if not branch:
            print("Specify branch")
            return

        r = requests.put(
            "http://{}/api/druid/branch/{}".format(self.host, branch),
            headers={"Token": self.token},
            data=""
        )
        print(loads(r.text))

    def complete_check_branch(self, text, line, begidx, endidx):
        """Автокомплит для команды check_branch."""
        if not text:
            completions = self.branches[:]
        else:
            completions = [
                f for f in self.branches if f.startswith(text)
            ]
        return completions

    def do_update_species(self, species):
        """Обработчик команды update_species.

        :param species: Имя обновляемого вида
        :type species: str
        """
        species = next(x for x in self.species if x["name"] == species)
        r = requests.patch(
            "http://{}/api/druid/species/{}".format(self.host, species["_id"]),
            headers={"Token": self.token},
            data=""
        )
        print(loads(r.text))

    def complete_update_species(self, text, line, begidx, endidx):
        """Автокомплит для команды update_species."""
        if not text:
            completions = [x["name"] for x in self.species]
        else:
            completions = [
                f["name"] for f in self.species if f["name"].startswith(text)
            ]
        return completions

    def do_create_leaf(self, args):
        """Обработчик команды create_leaf."""
        leaf_name, leaf_type, leaf_address = args.split()
        if not all([leaf_name, leaf_type, leaf_address]):
            print("Specify all args")
            return

        r = requests.post(
            "http://{}/api/druid/leaf".format(self.host),
            headers={"Token": self.token},
            data=dumps({
                "name": leaf_name,
                "type": leaf_type,
                "address": leaf_address
            })
        )
        print(loads(r.text))

    def complete_create_leaf(self, text, line, begidx, endidx):
        """Автокомплит для команды create_leaf."""
        if len(line.split(" ")) == 3:
            # Комплитим только второй аргумент - инстанс
            return [
                f["name"] for f in self.species if f["name"].startswith(text)
            ]
        else:
            return []

    def do_set_token(self, token):
        """Устанавливает секретный ключ для связи с брокером.

        :param token: Секретный ключ
        :type token: str
        """
        self.token = token

    def do_EOF(self, *args, **kwargs):
        """Обработчик EOF."""
        print()
        return True


if __name__ == '__main__':
    ShellTool().cmdloop()
