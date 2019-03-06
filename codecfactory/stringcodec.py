from codecfactory.basecodec import BaseCodec, ReadBuffer
from codecfactory.exc import (DecodeError, NoMatch, UnexpectedEndOfData, ExcessData,
                 EncodeError, EncodeMatchError)
import regex
import sys
__all__ = ["StringCodec", "pystringcodec"]

if sys.version_info.major >= 3:
    strtype = str
else:
    strtype = (str, unicode)


class StringCodec(BaseCodec):
    def __init__(self, decode_string_match, unescape_char_match, unescape_func,
                 escape_char_match, escape_func,
                 begin_delim='"', end_delim='"',
                 hook=None, unhook=None, allowedtype=strtype,
                 name="StringCodec"):
        """
        Codec for use in encoding/decoding strings.

        'decode_string_match': Regular expression used to match an entire encoded
        string (except for the enclosing delimiters). In a well-behaved implemenation
        of this class, this regular expression must not match end_delim.

        'unescape_char_match': Regular expression used to match escape sequences.

        'unescape_func': Function used to perform replacement of escape sequences
        via unescape_char_match.sub.

        'escape_char_match': Regular expression used to match characters to be
        replaced with escape sequences. This regular expression must match
        end_delim and any escape character, as well as any characters *not* matched
        by decode_string_match.

        'escape_func': Function used to perform replacement of characters with
        escape sequences via escape_char_match.sub.

        The 'pystringcodec' is an implementation of this class that encodes/decodes
        python strings.
        """
        self.decode_string_match = decode_string_match
        self.unescape_char_match = unescape_char_match
        self.unescape_func = unescape_func

        self.escape_char_match = escape_char_match
        self.escape_func = escape_func

        self.begin_delim = begin_delim
        self.end_delim = end_delim

        BaseCodec.__init__(self, hook=hook, unhook=unhook,
                           allowedtype=allowedtype, name=name)

    def _decode(self, string, offset):
        if not string[offset:].startswith(self.begin_delim):
            raise NoMatch(self)
        offset += len(self.begin_delim)

        match = self.decode_string_match.match(string, pos=offset, partial=True)

        if match is None:
            raise DecodeError(self, "Unable to match string.")
        elif match.partial:
            raise UnexpectedEndOfData(self, "Unexpected end of data encountered while attempting to decode string.")

        retstring = self.unescape_char_match.sub(self.unescape_func, match.group())
        offset = match.end()

        if not string[offset:].startswith(self.end_delim):
            raise DecodeError(self, "Unexpected character, escape sequence, or missing end delimiter.")
        offset += len(self.end_delim)

        return retstring, offset
        

    def _encode(self, string, indent="    ", indentlevel=0):
        encodedstring = self.escape_char_match.sub(self.escape_func, string)
        return self.begin_delim + encodedstring + self.end_delim


escape_codes={"r": "\r", "n": "\n", "t": "\t", "a": "\a", "b": "\b", "f": "\f", "\\": "\\", "\"": "\""}
escaped_escapes = regex.escape("".join(escape_codes.values()))
rescape_codes = {val: key for key, val in escape_codes.items()}
unescape_char_match = regex.compile(r"\\([%s]|x([0-f]{2})|u([0-f]{4})|U([0-f]{8}))" % regex.escape("".join(escape_codes.keys())))
decode_string_match = regex.compile(r"(?:\\(?:[%s]|x[0-f]{2}|u[0-f]{4}|U[0-f]{8})|[^%s\x00-\x1f\x7f-\U0010ffff])*" % (
                                    regex.escape("".join(escape_codes.keys())), regex.escape("".join(escape_codes.values()))
                                    ))
escape_char_match = regex.compile(r"[%s\x00-\x1f\x7f-\U0010ffff]" % regex.escape("".join(escape_codes.values())))

def encode_char(match):
    char = match.group()
    try:
        return "\\" + rescape_codes[char]
    except KeyError:
        n = ord(char)
        if n <= 32 or (127 <= n < 256):
            return r"\x%02x" % n
        elif 256 <= n < 65536:
            return r"\u%04x" % n
        elif n >= 65536:
            return r"\U%08x" % n

def decode_char(match):
    escape_char, xparams, uparams, Uparams = match.groups()
    try:
        return escape_codes[escape_char]
    except KeyError:
        if escape_char.startswith("x"):
            n = int(xparams, 16)
            return (chr if n < 128 else unichr)(n)
        elif escape_char.startswith("u"):
            return unichr(int(uparams, 16))
        elif escape_char.startswith("U"):
            return unichr(int(Uparams, 16))

pystringcodec = StringCodec(decode_string_match, unescape_char_match, decode_char,
                 escape_char_match, encode_char,
                 name="PythonStringCodec")
