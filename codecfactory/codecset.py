from basecodec import BaseCodec, ReadBuffer, skip_whitespace
from exc import *

__all__ = ["CodecSet"]

class CodecSet(BaseCodec):
    """Matches"""
    def __init__(self, codecs=[], name="CodecSet"):
        self.codecs = list(codecs)

    def _decode(self, data, offset=0):
        for codec in self.codecs:
            try:
                return codec.decodeone(data, offset)
            except NoMatch:
                continue
        else:
            raise NoMatch(self)

    def _encode(self, obj, indent="    ", indentlevel=0):
        for codec in self.codecs:
            if codec.validate_for_encode(obj):
                return codec.encode(obj, indent=indent, indentlevel=indentlevel)
        else:
            raise EncodeMatchError(self, obj, "No codec found for '%s' object." % type(obj).__name__)

    def _encode_to_file(self, obj, file, indent="    ", indentlevel=0, initialindent=None):
        for codec in self.codecs:
            if codec.validate_for_encode(obj):
                return codec.encode_to_file(obj, file, indent, indentlevel, initialindent)
        else:
            raise EncodeMatchError(self, obj, "No codec found for '%s' object." % type(obj).__name__)

    def appendCodec(self, codec):
        self.codecs.append(codec)
    def insertCodec(self, index, codec):
        self.codecs.insert(index, codec)
    def removeCodec(self, codec):
        self.codecs.remove(codec)
