#!/usr/bin/python
from basecodec import BaseCodec, SINGLE
from exc import *
import regex

__all__ = ["RegExCodec"]

class RegExCodec(BaseCodec):
    def __init__(self, regex, hook=None, hookmatch=False, unhook=None, strip_whitespace=True, allowedtype=None, name="RegExCodec"):
        self.regex = regex
        self.hook = hook
        if callable(hook):
            self.hook_mode = SINGLE
        self.hookmatch = hookmatch
        self.unhook = unhook
        self.strip_whitespace = strip_whitespace
        self.allowedtype = allowedtype
        self.name = name
    def _decode(self, string, offset=0):
        match = self.regex.match(string, pos=offset, partial=False)

        if match is None:
            raise NoMatch(self)

        if self.hookmatch:
            return match, match.end()

        return match.group(), match.end()

    def _decode_from_file(self, data, offset):
        match = data.regex_op(self.regex.match, string, pos=offset, partial=False)

        if match is None:
            raise NoMatch(self)

        if self.hookmatch:
            return match, match.end()

        return match.group(), match.end()

    def _encode(self, obj, file=None, indent="    ", indentlevel=0):
        if not isinstance(obj, (str, unicode)):
            raise EncodeTypeError(self, obj, "Can only encode strings. Please set an unhook attribute to fix this.")
        return obj
