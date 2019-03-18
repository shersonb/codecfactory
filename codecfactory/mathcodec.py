#!/usr/bin/python
from codecfactory.basecodec import (BaseCodec, ReadBuffer, skip_whitespace,
                                    NOHOOK, SINGLE, ARGS, KWARGS)
from codecfactory.exc import DecodeError, NoMatch, UnexpectedEndOfData, ExcessData, EncodeError, EncodeMatchError
from codecfactory.stringcodec import pystringcodec
from codecfactory.codecset import CodecSet
from codecfactory.numeralcodecs import (uintcodec, intcodec, floatcodec, rationalcodec, realcodec)
from codecfactory.listcodec import ListCodec
from codecfactory.dictcodec import DictCodec
from codecfactory.regexcodec import RegExCodec
import regex
import sympy
import sys

class VarArgOpDecoder(BaseCodec):
    hook_mode = ARGS
    def __init__(self, operator, invoperator=None, hook=None, invhook=None, operand_decoder=None, name="VarArgOpDecoder"):
        u"""
        Infix operator decoder.
        'operator': String used to indicate binary operation, e.g., "+".
        'invoperator': If specified, string used to indicate the inverse operation, e.g., "-". Should be used in the same decoder so
            that left-to-right order of operations between both a binary operation and its inverse is maintained.
        'hook': Can be either a scipy or SAGE function, or any function to handle the operation.
        'invhook': Function to be applied to operands immediately following occurence of 'invoperator'.
        'operand_decoder': Codec used to decode operands.
        """
        self.operator = operator
        self.invoperator = invoperator
        self.invhook = invhook
        self.operand_decoder = operand_decoder

        BaseCodec.__init__(self, hook=hook, name=name)

    def _decode(self, readbuf, offset=0, discardbufferdata=None):
        results = []
        item, offset = self.operand_decoder.decodeone(readbuf, offset, discardbufferdata)
        results.append(item)
        while True:
            offset = skip_whitespace(readbuf, offset, False)
            if readbuf.string_match(self.operator, offset):
                try:
                    item, offset = self.operand_decoder.decodeone(readbuf, offset+len(self.operator), discardbufferdata)
                except NoMatch:
                    if offset < len(readbuf.data):
                        lineno, char = readbuf.abspos(offset)
                        raise DecodeError(self,
                                "Unexpected character while trying to decode operand on line %d, character %d (expecting an operand, got '%s')." % (
                                lineno, char, readbuf.data[offset:offset+16]), readbuf.absoffset(offset))
                    raise UnexpectedEndOfData(self, "Unexpected end of data (expecting an operand).")
                results.append(item)
            elif self.invoperator is not None and readbuf.string_match(self.invoperator, offset):
                try:
                    item, offset = self.operand_decoder.decodeone(readbuf, offset+len(self.invoperator), discardbufferdata)
                except NoMatch:
                    if offset < len(readbuf.data):
                        lineno, char = readbuf.abspos(offset)
                        raise DecodeError(self,
                                "Unexpected character while trying to decode operand on line %d, character %d (expecting an operand, got '%s')." % (
                                lineno, char, readbuf.data[offset:offset+16]), readbuf.absoffset(offset))
                    raise UnexpectedEndOfData(self, "Unexpected end of data (expecting an operand).")
                results.append(self.invhook(item))
            else:
                return results, offset

class UnaryOpDecoder(BaseCodec):
    hook_mode = SINGLE
    def __init__(self, operator, hook=None, operand_decoder=None, vararg=True, name="UnaryOpDecoder"):
        u"""
        Prefix operator decoder.
        'operator': String used to indicate unary operation, e.g., "-".
        'hook': Can be either a scipy or SAGE function, or any function to handle the operation.
        'operand_decoder': Codec used to decode operand.
        """
        self.operator = operator
        self.hook = hook
        self.operand_decoder = operand_decoder
        self.vararg = vararg
        self.name = name

    def _decode(self, readbuf, offset=0, discardbufferdata=None):
        offset = skip_whitespace(readbuf, offset, False)
        if readbuf.string_match(self.operator, offset):
            try:
                return self.operand_decoder.decodeone(readbuf, offset+len(self.operator), discardbufferdata)
            except NoMatch:
                if offset < len(readbuf.data):
                    lineno, char = readbuf.abspos(offset)
                    raise DecodeError(self,
                            "Unexpected character while trying to decode operand on line %d, character %d ('%s')." % (
                            lineno, char, readbuf.data[offset:offset+16]))
                raise UnexpectedEndOfData(self)
        raise NoMatch(self)


class RelationDecoder(BaseCodec):
    hook_mode = ARGS
    def __init__(self, relations, operand_decoder=None, name="BinOpDecoder"):
        u"""
        """
        self.relations = relations
        self.operand_decoder = operand_decoder

        BaseCodec.__init__(self, name=name)

    def _decode(self, readbuf, offset=0, discardbufferdata=None):
        lhs, offset = self.operand_decoder.decodeone(readbuf, offset)
        offset = skip_whitespace(readbuf, offset, False)
        for rel in sorted(self.relations.keys(), key=len, reverse=True):
            if readbuf.string_match(rel, offset):
                try:
                    rhs, offset = self.operand_decoder.decodeone(readbuf, offset+len(rel))
                except NoMatch:
                    if offset < len(readbuf.data):
                        lineno, char = readbuf.abspos(offset)
                        raise DecodeError(self,
                                "Unexpected character while trying to decode operand on line %d, character %d ('%s')." % (
                                lineno, char, readbuf.data[offset:offset+16]))
                    raise UnexpectedEndOfData(self)
                return [lhs, rel, rhs], offset
        else:
            return [lhs], offset

    def _hook(self, lhs, rel=None, rhs=None):
        if rel is None and rhs is None:
            return lhs
        return self.relations[rel](lhs, rhs)

def parenthesis_hook(args):
    if len(args) == 1:
        return args[0]
    else:
        return tuple(args)

def makemathdecoder(add, neg, mul, inv, pow, eq, le, ge, lt, gt, ne, varhook, fcnhook):
    name_decoder = RegExCodec(regex.compile("[A-Za-z][A-Za-z0-9]*"), name="NameDecoder")
    expr_decoder = CodecSet([], name="ExpressionDecoder")


    powdecoder = VarArgOpDecoder("^", hook=pow, operand_decoder=expr_decoder, name="PowDecoder")
    posdecoder = UnaryOpDecoder("+", operand_decoder=powdecoder, name="PosDecoder")
    negdecoder = UnaryOpDecoder("-", neg, operand_decoder=powdecoder, name="NegDecoder")
    prodquotdecoder = VarArgOpDecoder("*", "/", mul, inv, CodecSet([negdecoder, posdecoder, powdecoder]), name="ProdQuotDecoder")
    sumdiffdecoder = VarArgOpDecoder("+", "-", add, neg, prodquotdecoder, name="SumDiffDecoder")

    parenthesis_codec = ListCodec(sumdiffdecoder, hook=parenthesis_hook, begin_delim="(", item_delim=",", end_delim=")")
    reldecoder = RelationDecoder({"=": eq, "==": eq, ">": gt, "<": lt, ">=": ge, "<=": le, "!=": ne}, operand_decoder=sumdiffdecoder, name="RelationDecoder")

    fcncall_decoder = FunctionCallDecoder(name_decoder, parenthesis_codec, varhook, fcnhook)

    expr_decoder.appendCodec(parenthesis_codec)
    expr_decoder.appendCodec(negdecoder)
    expr_decoder.appendCodec(posdecoder)
    expr_decoder.appendCodec(fcncall_decoder)
    #expr_decoder.appendCodec(complexcodec)
    #expr_decoder.appendCodec(imagcodec)
    expr_decoder.appendCodec(floatcodec)
    expr_decoder.appendCodec(intcodec)

    return reldecoder



class FunctionCallDecoder(BaseCodec):
    hook_mode = ARGS
    """Decodes variables (x) and function calls (f(x))"""
    def __init__(self, name_decoder, args_decoder, var_hook=None, fcn_hook=None, name="FunctionCallDecoder"):
        self.name_decoder = name_decoder
        self.args_decoder = args_decoder
        self.var_hook = var_hook
        self.fcn_hook = fcn_hook
        self.name = name
        BaseCodec.__init__(self, name=name)


    def _decode(self, readbuf, offset=0, discardbufferdata=None):
        offset = skip_whitespace(readbuf, offset, False)
        name, offset = self.name_decoder.decodeone(readbuf, offset)
        try:
            args, offset = self.args_decoder.decodeone(readbuf, offset)
        except NoMatch:
            return [name], offset
        return [name, args], offset

    def _hook(self, f, x=None):
        if x is None:
            if callable(self.var_hook):
                return self.var_hook(f)
            return f
        f = self.fcn_hook(f)
        if isinstance(x, (list, tuple)):
            return f(*x)
        return f(x)
