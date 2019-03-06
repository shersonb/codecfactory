from codecfactory.regexcodec import RegExCodec
import regex
import fractions
from codecfactory.codecset import CodecSet
import sys

__all__ = ["uintcodec", "intcodec", "floatcodec", "rationalcodec", "realcodec"]

if sys.version_info.major >= 3:
    inttype = int
else:
    inttype = (int, long)

uintcodec = RegExCodec(regex.compile("\d+"), hook=int, unhook=str, allowedtype=inttype, name="Unsigned Integer Codec")
intcodec = RegExCodec(regex.compile(r"[\+\-]?\d+"), hook=int, unhook=str, allowedtype=inttype, name="Signed Integer Codec")
floatcodec = RegExCodec(regex.compile(r"[\+\-]?(?:\d+\.\d*|\.\d+)(?:[Ee][\+\-]?\d+)?"), hook=float, unhook=str, allowedtype=float, name="Float Codec")
rationalcodec = RegExCodec(regex.compile(r"[\+\-]?\d+(?:/\d+)"), hook=fractions.Fraction, unhook="{0.numerator}/{0.denominator}".format, allowedtype=fractions.Fraction, name="Rational Codec")
realcodec = CodecSet([floatcodec, rationalcodec, intcodec], name="Real Number Codec")
