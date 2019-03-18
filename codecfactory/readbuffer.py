#!/usr/bin/python

__all__ = ["ReadBuffer"]

class ReadBuffer(object):
    """
    Class used to wrap around a file or file-like object so that objects can be decoded as soon as possible
    witout the need to read the entire file into memory.
    
    The basic idea is to read data one line at a time as it is needed for successive decode operations.
    A discard method is included so that data can be discarded when it is no longer needed.
    """
    def __init__(self, file, data=""):
        self._file = file
        self.data = data
        self.discarded = 0
        self.lines_discarded = 0
        self.discarded_on_current_line = 0

    def readdata(self, count=None):
        """Called when we need to read more data from the file object and append it to self.data."""
        if count is None:
            line = self._file.readline()
        else:
            line = self._file.read(count)
        self.data += line
        if line == "":
            self._file.close()
        return len(line)

    def discard(self, offset):
        """We may not necessarily want to keep all the raw data from the file, so we may periodically
        wish to discard the data once it has been decoded and processed. This is to help keep self.data
        relatively small."""
        tobediscarded = self.data[:offset]
        self.data = self.data[offset:]
        self.discarded += len(tobediscarded)
        self.lines_discarded += tobediscarded.count("\n")
        if "\n" in tobediscarded:
            self.discarded_on_current_line = len(tobediscarded) - tobediscarded.rindex("\n") + 1
        else:
            self.discarded_on_current_line += len(tobediscarded)

    def absoffset(self, offset):
        return self.discarded + offset

    def abspos(self, offset):
        lc = self.data.count("\n", 0, offset)
        lineno = self.lines_discarded + lc + 1
        if lc:
            char = offset - self.data.rfind("\n", 0, offset)
        else:
            char = self.discarded_on_current_line + offset + 1
        return (lineno, char)

    def regex_op(self, re_method, pos=None, endpos=None, concurrent=None):
        """
        Special: Apply a regular expression search on the file. The support in the regex module for
        indicating a partial match allows us to determine that a match may be possible if more data is read
        from the file.
        """
        while True:
            result = re_method(self.data, pos=pos, endpos=endpos, concurrent=concurrent, partial=True)
            if result is None:
                """No match, no possibilty of a partial match."""
                return None
            elif result.end() < len(self.data):
                """
                A match is found, and it ends before the end of the current data.
                result.partial == False implied.
                """
                return result
            elif self._file.closed or self.readdata(1024) == 0:
                """
                File object is closed (or at least will be if self.readdata() is called and no data is read). At this point, the match is either complete and ends at the end of the file,
                or it is a partial match. If the match is flagged as partial, the match could still be complete, but
                we won't know that until we rerun the method with partial=False. If the match is a partial, but
                incomplete, there is no hope of obtaining a complete match."""
                if not result.partial:
                    """We do not need to rerun the re_method."""
                    return result
                return re_method(self.data, pos=pos, endpos=endpos, concurrent=concurrent, partial=False)

    def string_match(self, string, offset):
        if offset + len(string) > len(self.data) and not self._file.closed:
            self.readdata(offset + len(string) - len(self.data))
        return self.data[offset:].startswith(string)
