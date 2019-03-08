from codecfactory.basecodec import (BaseCodec, ReadBuffer, skip_whitespace,
                                    NOHOOK, SINGLE, ARGS, KWARGS)
from codecfactory.exc import (DecodeError, NoMatch, UnexpectedEndOfData, ExcessData,
                 EncodeError, EncodeMatchError)
import inspect
import types
from collections import OrderedDict

class ListCodec(BaseCodec):
    def __init__(self,
                 item_codec, codecs_by_index={},
                 begin_delim="[", item_delim=",", end_delim="]",
                 hook=None, unhook=None, hook_mode=None, allowedtype=(list, tuple),
                 notify_encode=None, notify_decode=None,
                 multiline=True,
                 skip_whitespace_between_items=True,
                 discardbufferdata=True
                 ):
        """
        'item_codec': Default codec used to encode/decode items in list.
        'codecs_by_index': Specify codecs to use for specific indices (overriding
            item_codec).
        'begin_delim': Character or string used to mark beginning of list. If
            strip_whitespace == True, this parameter should NOT start with any
            whitespace!
        'item_delim': Character or string used in between items in list. If
            skip_whitespace_between_items == True, this parameter should NOT
            start with any whitespace!
        'end_delim': Character or string used to mark end of list. If
            skip_whitespace_between_items == True, this parameter should NOT
            start with any whitespace!
        'notify_encode': If a callable function is passed, this function is run each
            time an item is encoded, with the original object passed as a parameter.
        'notify_decode': If a callable function is passed, this function is run each
            time an item is decoded, with the decoded object passed as a parameter.
        'multiline': If True, lists will be encoded as multi-line strings, starting each
            item on a new line. Note that multiline = True is incompatible with
            skip_whitespace_between_items = False.
        'skip_whitespace_between_items': If True, will strip white space before and
            after items and item_delim inside the list. If item codecs have
            strip_whitespace set to True, then this will only have the effect of not
            stripping whitespace preceding item_delim.
        'allowedtype', 'hook', 'unhook', and 'hook_mode' retain their meaning from
            BaseCodec. If 'unhook' is not specified, it defaults to the instance method.
        """
        self.multiline = bool(multiline) # Write one line per item in encoding.

        self.notify_encode = notify_encode
        self.notify_decode = notify_decode

        self.item_codec = item_codec
        self.codecs_by_index = dict(codecs_by_index)

        self.begin_delim = begin_delim
        self.end_delim = end_delim
        self.item_delim = item_delim
        
        self.skip_whitespace_between_items = bool(skip_whitespace_between_items)
        BaseCodec.__init__(self, hook=hook, unhook=unhook, hook_mode=hook_mode,
                           allowedtype=allowedtype, discardbufferdata=discardbufferdata)

    def _match_delim(self, readbuf, delim, offset=0):
        if self.skip_whitespace_between_items:
            offset = skip_whitespace(readbuf, offset, False)

        while offset + len(delim) > len(readbuf.data) and not readbuf._file.closed:
            readbuf.readdata()

        if offset > len(readbuf.data):
            raise UnexpectedEndOfData(self, "Unexpected end of string while decoding list.")

        elif readbuf.data[offset:].startswith(delim):
            return offset + len(delim)

        raise NoMatch(self)

    def _match_begin_delim(self, readbuf, offset=0):
        offset = self._match_delim(readbuf, self.begin_delim, offset)
        return offset

    def _match_item_delim(self, readbuf, offset=0):
        offset = self._match_delim(readbuf, self.item_delim, offset)
        return offset

    def _match_end_delim(self, readbuf, offset=0):
        offset = self._match_delim(readbuf, self.end_delim, offset)
        return offset

    def _decode_item(self, readbuf, offset=0, k=None, discardbufferdata=None):
        codec = self.codecs_by_index.get(k, self.item_codec)
        return codec.decodeone(readbuf, offset, discardbufferdata=discardbufferdata)

    def _decode(self, readbuf, offset=0, discardbufferdata=None):
        offset = self._match_begin_delim(readbuf, offset)

        results = []
        k = 0
        while True:
            if len(self.end_delim):
                """If list is empty, we expect to find end_delim next."""
                try:
                    offset = self._match_end_delim(readbuf, offset)
                except NoMatch:
                    pass
                else:
                    return results, offset

            if self.skip_whitespace_between_items:
                offset = skip_whitespace(readbuf, offset)

            try:
                item, offset = self._decode_item(readbuf, offset, k, discardbufferdata=discardbufferdata)
            except NoMatch:
                lineno, char = readbuf.abspos(offset)
                raise DecodeError(self, "Unexpected character or item on line %d, character %d ('%s')." % (
                    lineno, char, readbuf.data[offset:offset+16]), readbuf.absoffset(offset))

            results.append(item)
            k += 1

            if callable(self.notify_decode):
                self.notify_decode(item)

            try:
                offset = self._match_item_delim(readbuf, offset)
            except NoMatch:
                try:
                    offset = self._match_end_delim(readbuf, offset)
                except NoMatch:
                    lineno, char = readbuf.abspos(offset)
                    raise DecodeError(self, "Unexpected character on line %d, character %d ('%s')." % (
                        lineno, char, readbuf.data[offset:offset+16]), offset)
                return results, offset

    def _encode_item(self, obj, file=None, indent="    ", indentlevel=0, indentfirstline=True, k=None):
        codec = self.codecs_by_index.get(k, self.item_codec)
        return codec.encode(obj, file, indent, indentlevel, indentfirstline)

    def _encode_multiline(self, obj, file, indent="    ", indentlevel=0):
        if len(self.begin_delim):
            file.write(self.begin_delim)
        for k, item in enumerate(obj):
            if k > 0:
                file.write(self.item_delim + "\n")
            else:
                file.write("\n")
            self._encode_item(item, file=file, indent=indent, indentlevel=indentlevel+1,
                                                 indentfirstline=True, k=k)
        file.write("\n" + indent*indentlevel + self.end_delim)

    def _encode_singleline(self, obj, file, indent="    ", indentlevel=0):
        if len(self.begin_delim):
            file.write(self.begin_delim)
        for k, item in enumerate(obj):
            if k > 0:
                if self.skip_whitespace_between_items:
                    file.write(self.item_delim + " ")
                else:
                    file.write(self.item_delim)
            self._encode_item(item, file=file, indent=indent, indentlevel=indentlevel+1,
                                                 indentfirstline=False, k=k)
        if len(self.end_delim):
            file.write(self.end_delim)

    def _encode(self, obj, file, indent="    ", indentlevel=0):
        if self.multiline and self.skip_whitespace_between_items:
            return self._encode_multiline(obj, file, indent, indentlevel)
        return self._encode_singleline(obj, file, indent, indentlevel)

    def _unhook(self, obj):
        suggestion = "Please implement a custom unhook function, or a 'getinitargs' method or list for this class."
        if isinstance(obj, (list, tuple)):
            return list(obj)
        elif hasattr(obj, "getinitargs"):
            if callable(obj.getinitargs):
                """
                Assume obj.getinitargs is an instance method that returns a list of arguments that
                returns a list of args that can be used to recreate obj using obj.__class__(*args).
                """
                return obj.getinitargs()
            elif isinstance(obj.getinitargs, (list, tuple)):
                """
                Assume obj.getinitargs is a list of attribute names that 
                """
                return [getattr(obj, attr) for attr in obj.getinitargs]
            else:
                raise EncodeError(self, obj, "Do not know how to work with 'getinitargs' object for '%s' object." % obj.__class__.__name__)
        elif hasattr(obj, "__init__") and isinstance(obj.__init__, types.MethodType):
            try:
                argspec = inspect.getargspec(obj.__init__)
            except:
                raise EncodeError(self, obj,
                        "Unable to determine initialization arguments for '%s' object. %s" %
                        obj.__class__.__name__, suggestion)
            if argspec.varargs is not None:
                raise EncodeError(self, obj,
                        "Cowardly refusing to unhook '%s' object containing 'varargs' in its initialization arguments. %s" %
                        obj.__class__.__name__, suggestion)
            if argspec.keywords is not None:
                raise EncodeError(self, obj,
                        "Cowardly refusing to unhook '%s' object containing 'keywords' in its initialization arguments. %s" %
                        obj.__class__.__name__, suggestion)
            return [getattr(obj, attr) for attr in argspec.args[1:]]
        raise EncodeError(self, obj,
                "Unable to determine initialization arguments for '%s' object. %s" %
                obj.__class__.__name__, suggestion)
