from regexcodec import RegExCodec
import regex
import fractions
from codecset import CodecSet

__all__ = ["uintcodec", "intcodec", "floatcodec", "rationalcodec", "realcodec"]

uintcodec = RegExCodec(regex.compile("\d+"), hook=int, unhook=str, allowedtype=(int, long), name="Unsigned Integer Codec")
intcodec = RegExCodec(regex.compile(r"[\+\-]?\d+"), hook=int, unhook=str, allowedtype=(int, long), name="Signed Integer Codec")
floatcodec = RegExCodec(regex.compile(r"[\+\-]?(?:\d+\.\d*|\.\d+)(?:[Ee][\+\-]?\d+)?"), hook=float, unhook=str, allowedtype=float, name="Float Codec")
rationalcodec = RegExCodec(regex.compile(r"[\+\-]?\d+(?:/\d+)"), hook=fractions.Fraction, unhook="{0.numerator}/{0.denominator}".format, allowedtype=fractions.Fraction, name="Rational Codec")
realcodec = CodecSet([floatcodec, rationalcodec, intcodec], name="Real Number Codec")
