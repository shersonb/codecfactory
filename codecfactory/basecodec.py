#!/usr/bin/python
from exc import *
import regex as re

__all__ = ["BaseCodec", "ws_match", "skip_whitespace", "NOHOOK", "SINGLE", "ARGS", "KWARGS", "ALLATONCE", "PIECEBYPIECE"]

ws_match = re.compile(r'[ \t\n\r]*', flags=re.VERBOSE | re.MULTILINE | re.DOTALL)

class ReadBuffer(object):
    """
    Class used to wrap around a file or file-like object so that objects can be decoded as soon as possible
    witout the need to read the entire file into memory.
    
    The basic idea is to read data one line at a time as it is needed for successive decode operations.
    A discard method is included so that data can be discarded when it is no longer needed.
    """
    def __init__(self, file, data=""):
        self._file = file
        self.data = data
        self.discarded = 0

    def readdata(self):
        """Called when we need to read more data from the file object and append it to self.data."""
        line = self._file.readline()
        self.data += line
        if line == "":
            self._file.close()
        return len(line)

    def discard(self, offset):
        """We may not necessarily want to keep all the raw data from the file, so we may periodically
        wish to discard the data once it has been decoded and processed. This is to help keep self.data
        relatively small."""
        self.data = self.data[offset:]
        self.discarded += offset

    def regex_op(self, re_method, pos=None, endpos=None, concurrent=None):
        """
        Special: Apply a regular expression search on the file. The support in the regex module for
        indicating a partial match allows us to determine that a match may be possible if more data is read
        from the file.
        """
        while True:
            result = re_method(self.data, pos=pos, endpos=endpos, concurrent=concurrent, partial=True)
            if result is None:
                """No match, no possibilty of a partial match."""
                return None
            elif result.end() < len(self.data):
                """
                A match is found, and it ends before the end of the current data.
                result.partial == False implied.
                """
                return result
            elif self._file.closed or self.readdata() == 0:
                """
                File object is closed (or at least will be if self.readdata() is called and no data is read). At this point, the match is either complete and ends at the end of the file,
                or it is a partial match. If the match is flagged as partial, the match could still be complete, but
                we won't know that until we rerun the method with partial=False. If the match is a partial, but
                incomplete, there is no hope of obtaining a complete match."""
                if not result.partial:
                    """We do not need to rerun the re_method."""
                    return result
                return re_method(self.data, pos=pos, endpos=endpos, concurrent=concurrent, partial=False)

def skip_whitespace(data, offset=0, discarddata=True):
    """Function used to skip over whitespace in data."""
    if isinstance(data, ReadBuffer):
        offset = data.regex_op(ws_match, pos=offset).end()
        if discarddata:
            data.discard(offset)
            return 0
    else:
        offset = ws_match.match(data, pos=offset).end()
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
        if self.hook_mode in (SINGLE, ARGS, KWARGS):
            return self.unhook(obj)
        return obj

    def _decode(self, string, offset=0):
        """
        Actual decoding goes on in this method. Accepts only string, buffer (python's built-in type),
        or unicode objects. This is a method to be overridden in subclasses.
        """
        raise DecodeError(self, "Not implemented: Please implement the '_decode' method.")

    def decodeone(self, data, offset=0):
        """
        Decodes one object from data, returns the object and offset of the end of the match.
        Use this method if you wish to decode an object, but expect to decode more afterwards.
        """
        # Trim leading whitespace.
        if self.strip_whitespace:
            offset = skip_whitespace(data, offset, self.discardbufferdata)

        # Pass to self._decode_from_file if data is a ReadBuffer object.
        if isinstance(data, ReadBuffer):
            obj, offset = self._decode_from_file(data, offset)
            if self.discardbufferdata:
                data.discard(offset)
                offset = 0

        # Otherwise, it is assumed data is str, buffer, or unicode, and gets passed to self._decode
        else:
            obj, offset = self._decode(data, offset)
        try:
            obj = self.applyhook(obj)
        except BaseException, exc:
            raise DecodeError(self, "Exception encountered while applying hook.", offset + (data.discarded if isinstance(data, ReadBuffer) else 0), exc)
        return obj, offset

    def decode(self, data):
        """
        Wraps around self.decodeone, and detects if there is excess data after the match.
        Strips leading and trailing whitespace if self.strip_whitespace == True.
        An exception will be raised if excess data is detected.
        """
        if hasattr(data, "read") and hasattr(data, "readline") and hasattr(data, "closed"):
            data = ReadBuffer(data)
        obj, offset = self.decodeone(data)
        # Trim trailing whitespace.
        if self.strip_whitespace:
            offset = skip_whitespace(data, offset, self.discardbufferdata)
        if isinstance(data, ReadBuffer):
            if len(data.data) > offset or (not data._file.closed and data.readdata() > 0):
                raise ExcessData(self,  data.discarded + offset)
        elif len(data) > offset:
            raise ExcessData(self, offset)
        return obj

    def _decode_from_file(self, data, offset):
        """
        Wraps around the _decode method, passing data from a ReadBuffer object. If
        UnexpectedEndOfData is raised, then it is assumed a match may still be possible,
        and so we call data.readdata() and try again.

        Without reimplementing this method in subclasses that contain child decoders, each
        child's _decode_from_file method is bypassed.
        """
        while True:
            try:
                return self._decode(data.data, offset)
            except UnexpectedEndOfData:
                if data.readdata() == 0 and data._file.closed:
                    raise
                continue
            except DecodeError, exc:
                raise DecodeError(exc.codec, exc.message, exc.offset + data.discarded, exc.exc)

    def _encode(self, obj, indent="    ", indentlevel=0):
        """
        Actual encoding goes on in this method. Returns only string or unicode objects. This is a
        method to be overridden in subclasses.

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
        """
        if not self.validate_for_encode(obj):
            raise EncodeMatchError, "Expected %s, got %s instead." % (self.allowedtype, type(obj))
        obj = self.reversehook(obj)

        if hasattr(file, "write"):
            if indentfirstline:
                file.write(indent*indentlevel)
            return self._encode_to_file(obj, file, indent, indentlevel)
        if indentfirstline:
            return indent*indentlevel + self._encode(obj, indent, indentlevel)
        else:
            return self._encode(obj, indent, indentlevel)

    def _encode_to_file(self, obj, file, indent="    ", indentlevel=0, indentfirstline=True):
        """
        Wraps around the _encode method, writing its output to file.
        
        Without reimplementing this method, the behavior of _encode_to_file is to encode the entire
        object to string, then writing the results to file. This behavior may be undesirable if the object
        is a list or dict with many items. As such, one may reimplement _encode_to_file to be able to
        make use of each child encoder's _encode_to_file method.
        """
        file.write(self._encode(obj, indent, initialindent))

    def __repr__(self):
        return "%s(%s)" % (self.__class__.__name__, self.name)
