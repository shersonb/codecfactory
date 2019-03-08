#!/usr/bin/python
from codecfactory.exc import DecodeError, NoMatch, UnexpectedEndOfData, ExcessData, EncodeError, EncodeMatchError
from codecfactory.stringcodec import pystringcodec
from codecfactory.codecset import CodecSet
from codecfactory.numeralcodecs import (uintcodec, intcodec, floatcodec, rationalcodec, realcodec)
from codecfactory.listcodec import ListCodec
from codecfactory.dictcodec import DictCodec
from codecfactory.regexcodec import RegExCodec
import regex

__all__ = ["jsoncodec"]

boolcodec = RegExCodec(regex.compile(r"(?:true|false)\b"),
                       hook={"true": True, "false": False}.__getitem__,
                       unhook={True: "true", False: "false"}.__getitem__,
                       allowedtype=bool)
nonecodec = RegExCodec(regex.compile(r"null\b"),
                       hook={"null": None}.__getitem__,
                       unhook={None: "null"}.__getitem__,
                       allowedtype=type(None))

jsoncodec = CodecSet([boolcodec, nonecodec, pystringcodec, realcodec])
listcodec = ListCodec(jsoncodec)
dictcodec = DictCodec(pystringcodec, jsoncodec)
jsoncodec.appendCodec(listcodec)
jsoncodec.appendCodec(dictcodec)

jsoncodecsl = CodecSet([boolcodec, nonecodec, pystringcodec, realcodec])
listcodecsl = ListCodec(jsoncodecsl, multiline=False, skip_whitespace_between_items=False)
dictcodecsl = DictCodec(pystringcodec, jsoncodecsl, multiline=False, skip_whitespace_between_items=False)
jsoncodecsl.appendCodec(listcodecsl)
jsoncodecsl.appendCodec(dictcodecsl)

