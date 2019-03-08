#!/usr/bin/python
from codecfactory.basecodec import BaseCodec, SINGLE
from codecfactory.exc import (DecodeError, NoMatch, UnexpectedEndOfData, ExcessData,
                 EncodeError, EncodeMatchError)
import regex
import sys

__all__ = ["RegExCodec"]

if sys.version_info.major >= 3:
    strtype = str
else:
    strtype = (str, unicode)

class RegExCodec(BaseCodec):
    def __init__(self, regex, hook=None, hookmatch=False, unhook=None, strip_whitespace=True, allowedtype=None, name="RegExCodec"):
        self.regex = regex
        self.hookmatch = hookmatch
        BaseCodec.__init__(self, hook=hook, unhook=unhook,
                           allowedtype=allowedtype, strip_whitespace=strip_whitespace, name=name)

    def _decode(self, readbuf, offset=0, discardbufferdata=None):
        match = readbuf.regex_op(self.regex.match, pos=offset)

        if match is None:
            raise NoMatch(self)

        if self.hookmatch:
            return match, match.end()

        return match.group(), match.end()

    def _encode(self, obj, file, indent="    ", indentlevel=0):
        if not isinstance(obj, strtype):
            raise EncodeTypeError(self, obj, "Can only encode strings. Please set an unhook attribute to fix this.")
        return file.write(obj)
