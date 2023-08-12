from enum import StrEnum
from io import SEEK_CUR
from struct import unpack
from typing import BinaryIO


class Endianness(StrEnum):
    BIG_ENDIAN = '>'
    LITTLE_ENDIAN = '<'


class EndiannessAwareReader:
    fp: BinaryIO
    endianness: Endianness

    def __init__(self, fp: BinaryIO, endianness: Endianness):
        self.fp = fp
        self.endianness = endianness

    def jump(self, position):
        self.fp.seek(position)

    def skip(self, bytes_number):
        self.fp.seek(bytes_number, SEEK_CUR)

    def get_current_pos(self) -> int:
        return self.fp.tell()

    def read_ui16(self) -> int:
        (num,) = unpack(self.endianness + "H", self.read_buffer(2))
        return num

    def read_i16(self) -> int:
        (num,) = unpack(self.endianness + "h", self.read_buffer(2))
        return num

    def read_ui32(self) -> int:
        (num,) = unpack(self.endianness + "I", self.read_buffer(4))
        return num

    def read_i32(self) -> int:
        (num,) = unpack(self.endianness + "i", self.read_buffer(4))
        return num

    def read_buffer(self, count) -> bytes:
        data = self.fp.read(count)
        return data

    def read_tag(self) -> str:
        tag = self.read_buffer(4)
        if self.endianness == Endianness.LITTLE_ENDIAN:
            tag = tag[::-1]
        return tag.decode("ascii")

    def read_string(self) -> str:
        length = self.read_ui32()
        return self.read_buffer(length).decode('ascii')
