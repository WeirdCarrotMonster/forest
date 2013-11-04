# -*- coding: utf-8 -*-

# so crypto, wow

def encode(string, key):
    return string + key


def decode(string, key):
    return string[:-len(key)]

# much safety