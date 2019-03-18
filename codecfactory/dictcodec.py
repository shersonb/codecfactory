from codecfactory.basecodec import (BaseCodec, ReadBuffer, skip_whitespace,
                                    NOHOOK, SINGLE, ARGS, KWARGS)
from codecfactory.exc import (DecodeError, NoMatch, UnexpectedEndOfData, ExcessData,
                 EncodeError, EncodeMatchError)
import inspect
import types
from collections import OrderedDict
from codecfactory.listcodec import ListCodec
from codecfactory.stringcodec import pystringcodec

__all__ = ["DictCodec"]

class DictCodec(ListCodec):
    def __init__(self,
                 key_codec, item_codec, codecs_by_key=OrderedDict(),
                 required_args=set(), optional_args=set(), allow_unknown=True,
                 begin_delim="{", item_delim=",", key_delim=":", end_delim="}",
                 hook=None, unhook=None, hook_mode=None,
                 requireclasskey=False, dicttype=dict,
                 notify_encode=None, notify_decode=None,
                 allowedtype=None, multiline=True,
                 skip_whitespace_between_items=True,
                 discardbufferdata=True,
                 name="DictCodec"
                 ):
        self.key_codec = key_codec
        self.codecs_by_key = codecs_by_key.copy()
        self.required_args = set(required_args)
        self.optional_args = set(optional_args)
        self.dicttype = dicttype
        self.requireclasskey = bool(requireclasskey)
        self.allow_unknown = allow_unknown

        self.key_delim = key_delim

        ListCodec.__init__(self,
                 item_codec=item_codec,
                 begin_delim=begin_delim, item_delim=item_delim, end_delim=end_delim,
                 allowedtype=allowedtype,
                 hook=hook, unhook=unhook, hook_mode=hook_mode,
                 notify_encode=notify_encode, notify_decode=notify_decode,
                 multiline=multiline, skip_whitespace_between_items=skip_whitespace_between_items,
                 discardbufferdata=discardbufferdata, name=name)

    def _decode_key(self, readbuf, offset=0, discardbufferdata=None):
        try:
            return self.key_codec.decodeone(readbuf, offset, discardbufferdata=discardbufferdata)
        except NoMatch:
            lineno, char = readbuf.abspos(offset)
            raise DecodeError(self,
                              "Unexpected character while trying to decode key on line %d, character %d ('%s')." % (
                lineno, char, readbuf.data[offset:offset+16]))

    def _match_key_delim(self, readbuf, offset=0):
        offset = self._match_delim(readbuf, self.key_delim, offset)
        return offset

    def _match_class(self, string):
        if string != "%s.%s" % (self.allowedtype.__module__, self.allowedtype.__name__):
            raise NoMatch(self)
        return True

    def _decode_item(self, readbuf, offset=0, key=None, discardbufferdata=None):
        if key == "class":
            codec = pystringcodec
            return codec.decodeone(readbuf, offset, discardbufferdata=False)
        else:
            codec = self.codecs_by_key.get(key, self.item_codec)
            return codec.decodeone(readbuf, offset, discardbufferdata=discardbufferdata)

    def _decode(self, readbuf, offset=0, discardbufferdata=None):
        offset = self._match_begin_delim(readbuf, offset)
        keys = []
        results = []
        classmatched = False
        while True:
            try:
                offset = self._match_end_delim(readbuf, offset)
            except NoMatch:
                pass
            else:
                if self.requireclasskey:
                    lineno, char = readbuf.abspos(offset - len(self.end_delim))
                    raise DecodeError(self, "Expected class keyword on line %d, character %d (got '%s' instead)." %
                                    (lineno, char, self.end_delim), readbuf.abspos(offset - len(self.end_delim)))
                break

            if self.skip_whitespace_between_items:
                offset = skip_whitespace(readbuf, offset)

            key, offset = self._decode_key(readbuf, offset, discardbufferdata=False)

            if not classmatched and len(results) == 0 and self.requireclasskey and key != "class":
                lineno, char = readbuf.abspos(offset)
                raise DecodeError(self, "Expected class keyword on line %d, character %d (got '%s' instead)." %
                                  (lineno, char, key), readbuf.abspos(offset))

            elif key in keys:
                lineno, char = readbuf.abspos(offset)
                raise DecodeError(self, "Keyword argument '%s' repeated on line %d, character %d." %
                                  (key, lineno, char), readbuf.abspos(offset))

            elif not (key in self.required_args or key in self.optional_args or self.allow_unknown):
                lineno, char = readbuf.abspos(offset)
                raise DecodeError(self, "Unexpected keyword argument '%s' on line %d, character %d." %
                                  (key, lineno, char), readbuf.abspos(offset))

            try:
                offset = self._match_key_delim(readbuf, offset)
            except NoMatch:
                lineno, char = readbuf.abspos(offset)
                raise DecodeError(self, "Unexpected character on line %d, character %d (got '%s', expected '%s')." % (
                    lineno, char, readbuf.data[offset], self.key_delim), readbuf.abspos(offset))

            if self.skip_whitespace_between_items:
                offset = skip_whitespace(readbuf, offset)

            try:
                value, offset = self._decode_item(readbuf, offset, key, discardbufferdata=discardbufferdata)
            except NoMatch:
                lineno, char = readbuf.abspos(offset)
                raise DecodeError(self, "Unexpected character or item on line %d, character %d ('%s')." % (
                    lineno, char, readbuf.data[offset:offset+16]), readbuf.absoffset(offset))

            #if not classmatched and self.requireclasskey and len(results) == 0:
            if not classmatched and self.requireclasskey and len(results) == 0:
                classmatched = self._match_class(value)
            else:
                results.append((key, value))
                keys.append(key)

                if self.notify_decode is not None:
                    self.notify_decode(key, value)

            try:
                offset = self._match_item_delim(readbuf, offset)
            except NoMatch:
                try:
                    offset = self._match_end_delim(readbuf, offset)
                except NoMatch:
                    lineno, char = readbuf.abspos(offset)
                    raise DecodeError(self, "Unexpected character on line %d, character %d (got '%s', expected '%s' or '%s')." % (
                            lineno, char, readbuf.data[offset], self.item_delim, self.end_delim), readbuf.abspos(offset))
                else:
                    break
        for key in self.required_args:
            if key not in keys:
                raise DecodeError(self, "Required key '%s' missing." % key, readbuf.abspos(offset))

        results = self.dicttype(results)
        return results, offset

    def _encode_key(self, key, file=None, indent="    ", indentlevel=0, indentfirstline=True):
        return self.key_codec.encode(key, file, indent, indentlevel, indentfirstline)

    def _encode_item(self, obj, file=None, indent="    ", indentlevel=0, key=None):
        if key == "class":
            codec = pystringcodec
        else:
            codec = self.codecs_by_key.get(key, self.item_codec)
        return codec.encode(obj, file, indent, indentlevel, indentfirstline=False)

    def _encode_multiline(self, obj, file, indent="    ", indentlevel=0):
        if len(self.begin_delim):
            file.write(self.begin_delim)
        K = 0
        if self.requireclasskey:
            file.write("\n")
            self._encode_key("class", file, indent, indentlevel=indentlevel + 1, indentfirstline=True)
            file.write(self.key_delim + " ")
            typestring = "%s.%s" % (self.allowedtype.__module__, self.allowedtype.__name__)
            pystringcodec.encode(typestring, file, indent, indentlevel=indentlevel + 1, indentfirstline=False)
            K = 1
        for k, (key, value) in enumerate(obj.items(), K):
            if k > 0:
                file.write(self.item_delim + "\n")
            else:
                file.write("\n")
            self._encode_key(key, file, indent, indentlevel=indentlevel + 1, indentfirstline=True)
            file.write(self.key_delim + " ")
            self._encode_item(value, file=file, indent=indent, indentlevel=indentlevel+1, key=key)
        file.write("\n" + indent*indentlevel + self.end_delim)

    def _encode_singleline(self, obj, file, indent="    ", indentlevel=0):
        if len(self.begin_delim):
            file.write(self.begin_delim)
        K = 0
        if self.requireclasskey:
            self._encode_key("class", file, indent, indentlevel=indentlevel + 1, indentfirstline=False)
            if self.skip_whitespace_between_items:
                file.write(self.key_delim + " ")
            else:
                file.write(self.key_delim)
            typestring = "%s.%s" % (self.allowedtype.__module__, self.allowedtype.__name__)
            pystringcodec.encode(typestring, file, indent, indentlevel=indentlevel + 1, indentfirstline=False)
            K = 1
        for k, (key, value) in enumerate(obj.items(), K):
            if k > 0:
                if self.skip_whitespace_between_items:
                    file.write(self.item_delim + " ")
                else:
                    file.write(self.item_delim)
            self._encode_key(key, file, indent, indentlevel=indentlevel + 1, indentfirstline=False)
            if self.skip_whitespace_between_items:
                file.write(self.key_delim + " ")
            else:
                file.write(self.key_delim)
            self._encode_item(value, file=file, indent=indent, indentlevel=indentlevel+1, key=key)
        file.write(self.end_delim)

    def addArgument(self, key, codec, required=True):
        self.codecs_by_key[key] = codec
        if required:
            self.required_args.add(key)
        else:
            self.optional_args.add(key)

    def _unhook(self, obj):
        suggestion = "Please implement a custom unhook function, or a 'getinitkwargs' method or list for this class."
        if hasattr(obj, "getinitkwargs") and not isinstance(obj.getinitkwargs, (list, tuple)):
            if callable(obj.getinitkwargs):
                """
                Assume obj.getinitkwargs is an instance method that returns a dict 'kwargs' that can be used to
                recreate obj using obj.__class__(**kwargs).
                """
                return obj.getinitkwargs()
            else:
                raise EncodeError(self, obj, "Do not know how to work with 'getinitargs' object for '%s' object." % obj.__class__.__name__)
        elif isinstance(obj, dict):
            return self.dicttype(obj)
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

            if hasattr(obj, "getinitkwargs") and isinstance(obj.getinitkwargs, (list, tuple)):
                args = obj.getinitkwargs
            else:
                args = argspec.args[1:]

            if argspec.defaults is not None:
                args_with_defaults = dict(zip(argspec.args[-len(argspec.defaults):], argspec.defaults))
            else:
                args_with_defaults = {}

            pairs = [(arg, getattr(obj, arg)) for arg in args]
            pairs = [(arg, value) for (arg, value) in pairs if arg not in args_with_defaults or value is not args_with_defaults.get(arg)]
            return OrderedDict(pairs)
        raise EncodeError(self, obj,
                "Unable to determine initialization arguments for '%s' object. %s" %
                obj.__class__.__name__, suggestion)
