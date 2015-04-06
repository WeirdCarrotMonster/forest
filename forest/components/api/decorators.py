# coding=utf-8
"""Описывает декораторы, используемые в описании методов API."""

from __future__ import unicode_literals, print_function
import simplejson as json
from tornado.gen import Return
from jsonschema import validate, ValidationError

import forest.jsonschema as global_schema
from forest.components.common import loads


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


def schema(argument=None):
    """Создает валидирующий схему декоратор.

    :param argument: Путь к описанию схемы
    :type argument: str
    """
    try:
        assert argument
        module, schema_descriptor = argument.split(".")
        module = global_schema.__getattribute__(module)
        schema_descriptor = module.__getattribute__(schema_descriptor)
    except AttributeError:
        raise Exception("Can't import schema: {}".format(argument))
    except ValueError:
        raise Exception("Invalid schema declaration: {}".format(argument))
    except AssertionError:
        schema_descriptor = {
            "$schema": "http://json-schema.org/draft-04/schema#",
            "id": "",
            "type": "object",
            "properties": {}
        }

    def real_decorator(function):
        def wrapper(self, *args, **kwargs):
            try:
                data = loads(self.request.body)
                validate(data, schema_descriptor)
            except ValidationError as e:
                self.set_status(400)
                self.finish({"result": "failure", "message": str(e)})
            else:
                data.update(kwargs)
                return function(self, *args, **data)
        return wrapper
    return real_decorator
