from codecfactory.basecodec import BaseCodec, ReadBuffer, skip_whitespace
from codecfactory.exc import DecodeError, NoMatch, UnexpectedEndOfData, ExcessData, EncodeError, EncodeMatchError

__all__ = ["CodecSet"]

class CodecSet(BaseCodec):
    """
    Matches any one codec in a provided list of codecs.

    Note: If a child codec has a further child codec, it is the child codec's responsibility
    to capture and handle it's child's NoMatch exceptions so that CodecSet only sees
    NoMatch exceptions raised by its immediate children. If CodecSet sees any NoMatch
    exception from any of its grandchildren, then this may hide actual decoding errors.]
    """
    def __init__(self, codecs=[], name="CodecSet"):
        self.codecs = list(codecs)
        self.name = name

    def _decode(self, readbuf, offset=0, discardbufferdata=None):
        for codec in self.codecs:
            try:
                return codec.decodeone(readbuf, offset, discardbufferdata=discardbufferdata)
            except NoMatch:
                continue
        else:
            raise NoMatch(self)

    def validate_for_encode(self, obj):
        for codec in self.codecs:
            if codec.validate_for_encode(obj):
                return True
        return False

    def _encode(self, obj, file, indent="    ", indentlevel=0):
        for codec in self.codecs:
            if codec.validate_for_encode(obj):
                return codec.encode(obj, file, indent, indentlevel, indentfirstline=False)
        else:
            raise EncodeMatchError(self, obj, "No codec found for '%s' object." % type(obj).__name__)

    def appendCodec(self, codec):
        self.codecs.append(codec)
    def insertCodec(self, index, codec):
        self.codecs.insert(index, codec)
    def removeCodec(self, codec):
        self.codecs.remove(codec)
