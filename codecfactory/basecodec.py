#!/usr/bin/python
from codecfactory.exc import DecodeError, NoMatch, UnexpectedEndOfData, ExcessData, EncodeError, EncodeMatchError
import regex as re
import sys
import io
from codecfactory.readbuffer import ReadBuffer

__all__ = ["BaseCodec", "ws_match", "skip_whitespace", "NOHOOK", "SINGLE", "ARGS", "KWARGS", "ALLATONCE", "PIECEBYPIECE"]

if sys.version_info.major >= 3:
    strtype = str
else:
    strtype = (str, unicode)

ws_match = re.compile(r'[ \t\n\r]*', flags=re.VERBOSE | re.MULTILINE | re.DOTALL)

def skip_whitespace(readbuf, offset=0, discarddata=True):
    """Function used to skip over whitespace in data."""
    offset = readbuf.regex_op(ws_match.match, pos=offset).end()

    if discarddata:
        readbuf.discard(offset)
        return 0

    return offset

NOHOOK = 0
SINGLE = 1
ARGS = 2
KWARGS = 3

ALLATONCE = 0
PIECEBYPIECE = 1

class BaseCodec(object):
    """
    Base class for codecs. Must reimplement the following methods:
    _decode (Returns a pair, decoded object, and end offset)
    _encode
    
    The methods _encode_to_file and _decode_to_file may be optionally be reimplemented.
    
    For similar reasons, one may wish to reimplement _decode_to_file as well.
    """
    name = "BaseCodec"

    hook = None
    unhook = None
    hook_mode = NOHOOK
    """If hook_mode in (SINGLE, ARGS, KWARGS), hook and unhook must be made callable functions."""
    
    allowedtype = None
    discardbufferdata = True
    strip_whitespace = True

    def __init__(self, hook=None, unhook=None, hook_mode=None, allowedtype=None,
                 discardbufferdata=None, strip_whitespace=None, name=None):
        if hook is None and hasattr(self, "_hook"):
            hook = self._hook

        if unhook is None and hasattr(self, "_unhook"):
            unhook = self._unhook

        if callable(hook):
            self.hook = hook
            if hook_mode is None and self.hook_mode is NOHOOK:
                self.hook_mode = SINGLE
            elif self.hook_mode is NOHOOK:
                self.hook_mode = hook_mode

        if callable(unhook):
            self.unhook = unhook

        if allowedtype is not None:
            self.allowedtype = allowedtype

        if discardbufferdata is not None:
            self.discardbufferdata = bool(discardbufferdata)

        if strip_whitespace is not None:
            self.strip_whitespace = bool(strip_whitespace)

        if name is not None:
            self.name = name

    def applyhook(self, obj):
        """
        Once data is decoded, one may choose to process the data, passing it to a function that will
        return the ultimate object we wish to obtain. This can often be a class, and the data is its __init__
        arguments.
        """
        if self.hook_mode == SINGLE:
            return self.hook(obj)
        elif self.hook_mode == ARGS:
            return self.hook(*obj)
        elif self.hook_mode == KWARGS:
            return self.hook(**obj)
        return obj

    def reversehook(self, obj):
        """
        To encode an object, we want to reverse the effect of self.applyhook first.
        """
        if callable(self.unhook):
            return self.unhook(obj)
        return obj

    def _decode(self, readbuf, offset=0, discardbufferdata=None):
        """
        Actual decoding goes on in this method. Accepts only string, buffer (python's built-in type),
        or unicode objects. This is a method to be overridden in subclasses.

        Parameter 'discardbufferdata' should be passed to child codecs and not be
        directly implemented here.
        """
        raise DecodeError(self, "Not implemented: Please implement the '_decode' method.")

    def decodeone(self, readbuf, offset=0, discardbufferdata=None):
        startabsoffset = readbuf.absoffset(offset)
        """
        Wraps around _decode, and automatically reads more data in from readbuf whenever
        needed, so that this does not need to be done when reimplementing _decode.

        Basic rule of thumb: Reimplement _decode, but always call decodeone.

        Decodes one object from data, returns the object and offset of the end of the match.
        Use this method if you wish to decode an object, but expect to decode more afterwards.
        """

        discardbufferdata = discardbufferdata if discardbufferdata is not None else self.discardbufferdata

        # Trim leading whitespace.
        if self.strip_whitespace:
            offset = skip_whitespace(readbuf, offset, discardbufferdata)

        while True:
            try:
                (obj, offset) = self._decode(readbuf, offset, discardbufferdata=discardbufferdata)
            except UnexpectedEndOfData:
                if readbuf._file.closed or readbuf.readdata() == 0:
                    raise
                continue
            else:
                break

        if discardbufferdata:
            readbuf.discard(offset)
            offset = 0

        endabsoffset = readbuf.absoffset(offset)

        try:
            obj = self.applyhook(obj)
        except BaseException as exc:
            raise DecodeError(self, "Exception encountered while applying hook.",
                              (startabsoffset, endabsoffset), exc)

        return obj, offset

    def decode(self, data):
        """
        Wraps around self.decodeone, and detects if there is excess data after the match.
        Strips leading and trailing whitespace if self.strip_whitespace == True.
        An exception will be raised if excess data is detected.
        """
        if isinstance(data, strtype):
            readbuf = ReadBuffer(io.StringIO(data))
        else:
            readbuf = ReadBuffer(data)

        obj, offset = self.decodeone(readbuf)
        # Trim trailing whitespace.
        if self.strip_whitespace:
            offset = skip_whitespace(readbuf, offset, self.discardbufferdata)

        if len(readbuf.data) > offset or (not readbuf._file.closed and readbuf.readdata() > 0):
            raise ExcessData(self, readbuf.discarded + offset)
        return obj

    def _encode(self, obj, file, indent="    ", indentlevel=0):
        """
        Actual encoding goes on in this method, and is written to file.

        The parameters indent and indentlevel are implemented here, except on the first line of
        data, which is implemented in self.encode (if initialindent is True). This implies indent is
        completely ignored here if the encoded data is a single line. If subclasses have child
        encoders, indent=indent and indentlevel=indentlevel+1 should be passed to each child's
        respective encode method.
        """
        raise EncodeError(self, obj, "Not implemented: Please implement the '_encode' method.")

    def validate_for_encode(self, obj):
        """
        Check to see if this data type is allowed for encode.
        Big warning: If self.hook is of type 'type' and the actual type of the obj is a proper subclass,
        encoding then decoding may not return the desired results!
        """
        return self.allowedtype is None or isinstance(obj, self.allowedtype)

    def encode(self, obj, file=None, indent="    ", indentlevel=0, indentfirstline=True):
        """
        Wraps around _encode. First validates data and reverses hook before performing encode.
        Indentation is specified here, but implemented in _encode.

        If file is specified, encoded data is written to file. Otherwise, it is implied that the encoded
        data is returned as a string.

        If file is not specified, then a temporary StringIO object is created to write to, and then the
        results are read back and returned.

        Note: In Python 3, some file objects will only accept 'bytes'-type data in their write methods.
        The remedy to this is to wrap such file objects in io.TextIOWrapper.
        """
        if not self.validate_for_encode(obj):
            raise EncodeMatchError(self, obj, "Expected %s, got %s instead." % (self.allowedtype, type(obj)))
        obj = self.reversehook(obj)

        if file is None:
            returnstring = True
            file = io.StringIO()
        else:
            returnstring = False

        if indentfirstline:
            file.write(indent*indentlevel)

        ret = self._encode(obj, file, indent, indentlevel)

        if returnstring:
            file.seek(0)
            return file.read()

        return ret

    def __repr__(self):
        return "%s(%s)" % (self.__class__.__name__, self.name)
