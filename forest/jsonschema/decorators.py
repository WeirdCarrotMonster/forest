# coding=utf-8
"""Декоратор, используемый для автоматической проверки входных данных в хендлерах Tornado."""

from __future__ import unicode_literals, print_function
from forest.components.common import loads, load
from simplejson import JSONDecodeError


from os.path import join, realpath, dirname

from jsonschema import validate, ValidationError


def schema(argument=None):
    """Создает валидирующий схему декоратор.

    :param argument: Путь к описанию схемы
    :type argument: str
    """
    try:
        assert argument
        schema = join(dirname(realpath(__file__)), "schema", "{}.json".format(argument))
        with open(schema, "r") as schema_file:
            schema_descriptor = load(schema_file)
    except IOError:
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
            except (ValidationError, JSONDecodeError) as e:
                self.set_status(400)
                self.finish({"result": "failure", "message": str(e)})
            else:
                data.update(kwargs)
                return function(self, *args, **data)
        return wrapper
    return real_decorator
