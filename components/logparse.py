# -*- coding: utf-8 -*-
import re


__all__ = ["logparse"]

res = [
    (
        re.compile("\[uwsgi-subscription for pid \d+\] (?P<address>\w.+) => new node: (?P<host>\w.+):(?P<port>\w+)"),
        {"log_type": "air_subscription"}
    ),
    (
        re.compile("\[uwsgi-subscription for pid \d+\] new pool: (?P<address>\w.+) \(hash key: \d+\)"),
        {"log_type": "air_new_pool"}
    ),
    (
        re.compile("\w+ - \[emperor\] vassal (?P<leaf>\w+)_\d+.ini is ready to accept requests"),
        {"log_type": "emperor_vassal_ready"}
    ),
    (
        re.compile("\w+ - \[emperor\] vassal (?P<leaf>\w+)_\d+.ini is now loyal"),
        {"log_type": "emperor_vassal_loyal"}
    ),
    (
        re.compile("\[Leaf (?P<log_source>\w+)\](?P<raw>.*)", re.S),
        {"log_type": "leaf.stdout_stderr"}
    )
]


def logparse(data):
    important = False
    parsed = {"raw": data}

    for reg, more in res:
        m = reg.match(data)
        if m:
            parsed = dict(m.groupdict().items() + more.items())

    return parsed, important