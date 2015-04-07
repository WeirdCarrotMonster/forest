# coding=utf-8
"""Описывает декораторы, используемые в описании методов API."""

from __future__ import unicode_literals, print_function
import simplejson as json
from tornado.gen import Return


def token_auth(f):
    """Добавляет функции проверку на аутентифицированность пользователя по токену.

    :param f: Декорируемая функция
    :type f: function
    """
    # TODO: описать требуемые для работы заголовки

    def wrapper(self, *args, **kwargs):
        """Декоратор функции."""
        if self.application.secret != self.request.headers.get("Token"):
            self.set_status(403)
            self.finish(json.dumps({
                "result": "error",
                "message": "Not authenticated"
            }))
            raise Return()
        else:
            return f(self, *args, **kwargs)

    return wrapper
