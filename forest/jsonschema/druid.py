# coding=utf-8


leaves = {
    "$schema": "http://json-schema.org/draft-04/schema#",
    "id": "",
    "type": "object",
    "properties": {
        "name": {
          "id": "/name",
          "type": "string"
        },
        "type": {
            "id": "/type",
            "type": "string"
        },
        "address": {
            "id": "/address",
            "type": "string"
        }
    },
    "required": [
        "name",
        "type",
        "address"
    ],
    "additionalProperties": False
}
