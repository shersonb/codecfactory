class DecodeError(BaseException):
    def __init__(self, codec, message, offset=None, exc=None):
        self.codec = codec
        self.offset = offset
        self.exc = exc
        super(DecodeError, self).__init__(message)

class NoMatch(DecodeError):
    """
    Used by a decoder only if it immediately decides the beginning of data is not what the decoder expects.
    Should NOT be used after a decoder has already started decoding any data structure with any sort of complexity.
    """
    def __init__(self, codec):
        super(NoMatch, self).__init__(codec, "No Match.")

class UnexpectedEndOfData(DecodeError):
    def __init__(self, codec):
        super(UnexpectedEndOfData, self).__init__(codec, "Unexpected end of data.")

class ExcessData(DecodeError):
    def __init__(self, codec, offset):
        super(ExcessData, self).__init__(codec, "Data continues past expected end.", offset)

class EncodeError(BaseException):
    def __init__(self, codec, obj, message):
        self.codec = codec
        self.obj = obj
        super(EncodeError, self).__init__(message)

class EncodeMatchError(EncodeError):
    def __init__(self, codec, obj, message):
        super(EncodeMatchError, self).__init__(codec, obj, message)
