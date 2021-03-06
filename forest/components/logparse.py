# coding=utf-8
"""Модуль парсеров строковых логов."""

import re
import base64
import bson


# pylint: disable=W0702


res = [
    (
        re.compile(
            "\[Leaf (?P<log_source>\w{24})\]"
            "\[Traceback (?P<traceback_id>\w{8}\-\w{4}\-\w{4}\-\w{4}\-\w{12})\](?P<traceback>.*)", re.S),
        {"log_type": "leaf.traceback"},
        {"traceback": base64.b64decode, "log_source": bson.objectid.ObjectId}
    ),
    (
        re.compile("\[Leaf (?P<log_source>\w{24})\](?P<raw>.*)", re.S),
        {"log_type": "leaf.stdout_stderr"},
        {"log_source": bson.objectid.ObjectId}
    )
]

res_emperor = [
    (
        re.compile("\w.+ - \[emperor\] vassal (?P<vassal>\w+).ini is ready to accept requests"),
        {"log_type": "emperor_vassal_ready"},
        {}
    ),
    (
        re.compile("\w.+ - \[emperor\] removed uwsgi instance (?P<vassal>\w+).ini"),
        {"log_type": "emperor_vassal_removed"},
        {}
    )
]


def logparse(data):
    """Парсит строковые логи листьев.

    :param data: Строка лога
    :type data: str
    :returns: Словарь обработанного лога
    :rtype: dict
    """
    parsed = {"raw": data}

    for reg, more, converters in res:
        m = reg.match(data)
        if m:
            parsed = dict(m.groupdict().items() + more.items())
            for key, converter in converters.items():
                try:
                    parsed[key] = converter(parsed[key])
                except:
                    pass
            break

    return parsed


def logparse_emperor(data):
    """Парсит строковые логи императора.

    :param data: Строка лога
    :type data: str
    :returns: Словарь обработанного лога
    :rtype: dict
    """
    parsed = {"raw": data}

    for reg, more, converters in res_emperor:
        m = reg.match(data)
        if m:
            parsed = dict(m.groupdict().items() + more.items())
            for key, converter in converters.items():
                try:
                    parsed[key] = converter(parsed[key])
                except:
                    pass
            break

    return parsed
