from codecfactory.basecodec import (BaseCodec, ReadBuffer, skip_whitespace, skip_whitespace_in_string,
                       skip_whitespace_in_file, NOHOOK, SINGLE, ARGS, KWARGS)
from codecfactory.exc import (DecodeError, NoMatch, UnexpectedEndOfData, ExcessData,
                 EncodeError, EncodeMatchError)

class ListCodec(BaseCodec):
    def __init__(self,
                 item_codec, codecs_by_index={},
                 begin_delim="[", item_delim=",", end_delim="]",
                 hook=None, unhook=None, hook_mode=None, allowedtype=(list, tuple),
                 notify_encode=None, notify_decode=None,
                 multiline=True,
                 skip_whitespace_between_items=True
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
            BaseCodec.
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
                           allowedtype=allowedtype)

    def _match_delim(self, string, delim, offset=0):
        if offset >= len(string):
            raise UnexpectedEndOfData(self, "Unexpected end of string while decoding list.")
        elif string[offset:].startswith(delim):
            return offset + len(delim)
        raise NoMatch(self)

    def _match_begin_delim(self, string, offset=0):
        offset = self._match_delim(string, self.begin_delim, offset)
        return offset

    def _match_item_delim(self, string, offset=0):
        offset = self._match_delim(string, self.item_delim, offset)
        return offset

    def _match_end_delim(self, string, offset=0):
        offset = self._match_delim(string, self.end_delim, offset)
        return offset

    def _match_delim_from_file(self, data, delim, offset=0):
        while len(data.data) < offset + len(delim) and not data._file.closed:
            data.readdata()
        return self._match_delim(data.data, delim, offset)

    def _match_begin_delim_from_file(self, data, offset=0):
        offset = self._match_delim_from_file(data, self.begin_delim, offset)
        return offset

    def _match_item_delim_from_file(self, data, offset=0):
        offset = self._match_delim_from_file(data, self.item_delim, offset)
        return offset

    def _match_end_delim_from_file(self, data, offset=0):
        offset = self._match_delim_from_file(data, self.end_delim, offset)
        return offset

    def decode_item(self, data, offset=0, k=None):
        codec = self.codecs_by_index.get(k, self.item_codec)
        return codec.decodeone(data, offset)

    def _decode_with_specified_match_methods(self, data, match_begin_delim, match_item_delim,
                                             match_end_delim, skip_whitespace, offset=0):
        offset = match_begin_delim(data, offset)

        results = []
        k = 0
        while True:
            if self.skip_whitespace_between_items:
                offset = skip_whitespace(data, offset)

            if len(self.end_delim):
                """If list is empty, we expect to find end_delim next."""
                try:
                    offset = match_end_delim(data, offset)
                except NoMatch:
                    pass
                else:
                    return results, offset

            if self.skip_whitespace_between_items:
                offset = skip_whitespace(data, offset)

            try:
                item, offset = self.decode_item(data, offset, k)
            except NoMatch:
                string = data.data if isinstance(data, ReadBuffer) else data
                lines = string[:offset].split("\n")
                raise DecodeError(self, "Unexpected character or item on line %d, character %d ('%s')." % (len(lines), len(lines[-1])+1, string[offset:offset+16]), offset)

            results.append(item)
            k += 1

            if callable(self.notify_decode):
                self.notify_decode(item)

            if self.skip_whitespace_between_items:
                offset = skip_whitespace(data, offset)

            try:
                offset = match_item_delim(data, offset)
            except NoMatch:
                try:
                    offset = match_end_delim(data, offset)
                except NoMatch:
                    string = data.data if isinstance(data, ReadBuffer) else data
                    lines = data[:offset].split("\n")
                    raise DecodeError(self, "Unexpected character on line %d, character %d ('%s')." % (
                        len(lines), len(lines[-1])+1, data[offset:offset+16]), offset)
                return results, offset

            if self.skip_whitespace_between_items:
                offset = skip_whitespace(data, offset)

    def _decode(self, string, offset=0):
        return self._decode_with_specified_match_methods(string, self._match_begin_delim,
                                    self._match_item_delim, self._match_end_delim, skip_whitespace_in_string, offset)

    def _decode_from_file(self, data, offset=0):
        return self._decode_with_specified_match_methods(data, self._match_begin_delim_from_file,
                                    self._match_item_delim_from_file, self._match_end_delim_from_file,
                                    skip_whitespace_in_file, offset)

    #def _encode_with_specified_match_methods(self, data, match_begin_delim, match_item_delim,
                                             #match_end_delim, skip_whitespace, offset=0):

    def encode_item(self, data, file=None, indent="    ", indentlevel=0, indentfirstline=True, k=None):
        codec = self.codecs_by_index.get(k, self.item_codec)
        return codec.encode(data, file, indent, indentlevel, indentfirstline)

    def _encode_multiline(self, obj, indent="    ", indentlevel=0):
        retstring = self.begin_delim
        for k, item in enumerate(obj):
            if k > 0:
                retstring += self.item_delim
            retstring += "\n" + self.encode_item(item, indent=indent, indentlevel=indentlevel+1,
                                                 indentfirstline=True)
        retstring += "\n" + indent*indentlevel + self.end_delim
        return retstring

    def _encode_singleline(self, obj, indent="    ", indentlevel=0):
        retstring = self.begin_delim
        for k, item in enumerate(obj):
            if k > 0:
                retstring += self.item_delim + " "
            retstring += self.encode_item(item, indent=indent, indentlevel=indentlevel+1,
                                                 indentfirstline=False)
        retstring += self.end_delim
        return retstring

    def _encode_multiline_to_file(self, obj, file, indent="    ", indentlevel=0):
        if len(self.begin_delim):
            file.write(self.begin_delim)
        for k, item in enumerate(obj):
            if k > 0:
                file.write(self.item_delim + "\n")
            else:
                file.write("\n")
            self.encode_item(item, file=file, indent=indent, indentlevel=indentlevel+1,
                                                 indentfirstline=True)
        file.write("\n" + indent*indentlevel + self.end_delim)

    def _encode_singleline_to_file(self, obj, file, indent="    ", indentlevel=0):
        if len(self.begin_delim):
            file.write(self.begin_delim)
        for k, item in enumerate(obj):
            if k > 0:
                file.write(self.item_delim + " ")
            self.encode_item(item, file=file, indent=indent, indentlevel=indentlevel+1,
                                                 indentfirstline=False)
        if len(self.end_delim):
            file.write(self.end_delim)

    def _encode(self, obj, indent="    ", indentlevel=0):
        if self.multiline:
            return self._encode_multiline(obj, indent, indentlevel)
        return self._encode_singleline(obj, indent, indentlevel)


    def _encode_to_file(self, obj, file, indent="    ", indentlevel=0):
        if self.multiline:
            return self._encode_multiline_to_file(obj, file, indent, indentlevel)
        return self._encode_singleline_to_file(obj, file, indent, indentlevel)


    #def encode_begin_delim(self, indent="    ", indentlevel=0):
        #return indent*indentlevel + self.begin_delim

    #def encode_item(self, item, indent="    ", indentlevel=0):
        #return self.item_codec.encode(item, indent, indentlevel+1)

    #def encode_end_delim(self, indent="    ", indentlevel=0):
        #return indent*indentlevel + self.end_delim

    #def encode(self, obj, indent="    ", indentlevel=0):
        #if self.allowedtype is not None and not isinstance(obj, self.allowedtype):
            #raise TypeError, "Expected %s, got %s instead." % (self.allowedtype, type(obj))
        #if self.multiline:
            #lines = [self.encode_begin_delim(indent, indentlevel)]
            #for k, item in enumerate(obj):
                #if k == len(obj) - 1:
                    #lines.append(self.item_codec.encode(item, indent, indentlevel+1))
                #else:
                    #lines.append(self.item_codec.encode(item, indent, indentlevel+1) + self.item_delim)
                #if self.notify_encode is not None:
                    #self.notify_encode(item)
            #lines.append(self.encode_end_delim(indent, indentlevel))
            #return "\n".join(lines)
        #else:
            #string = self.encode_begin_delim(indent, indentlevel)
            #for k, item in enumerate(obj):
                #string += self.item_codec.encode(item, indent, 0)
                #if self.notify_encode is not None:
                    #self.notify_encode(item)
                #if k < len(obj) - 1:
                    #string += self.item_delim
            #string += self.encode_end_delim(indent, 0)
            #return string
    #def encode_to_file(self, obj, file, indent="    ", indentlevel=0, initialindent=None):
        #initialindent = initialindent if initialindent is not None else indentlevel
        #if self.allowedtype is not None and not isinstance(obj, self.allowedtype):
            #raise TypeError, "Expected %s, got %s instead." % (self.allowedtype, type(obj))
        #if self.multiline:
            #print >>file, self.encode_begin_delim(indent, initialindent)
            #for k, item in enumerate(obj):
                #self.item_codec.encode_to_file(item, file, indent, indentlevel+1)
                #if k < len(obj) - 1:
                    #print >>file, self.item_delim
                #else:
                    #print >>file, ""
                #if self.notify_encode is not None:
                    #self.notify_encode(item)
            #file.write(self.encode_end_delim(indent, indentlevel))
        #else:
            #file.write(self.encode(obj), indent, initialindent)
