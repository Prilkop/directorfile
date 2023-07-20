from __future__ import annotations

from abc import ABCMeta, abstractmethod
from typing import BinaryIO, Optional, Sequence, Type

from directorfile.common import Endianness, EndiannessAwareReader


class Resource(metaclass=ABCMeta):
    _fp: BinaryIO
    _reader: EndiannessAwareReader
    position: int
    size: int

    def __init__(self, fp: BinaryIO, position: int, size: Optional[int] = None):
        self._fp = fp

        self._fp.seek(position)
        tag = self._fp.read(4).decode('ascii')

        if tag == self.TAG:
            endianness = Endianness.BIG_ENDIAN
        elif tag == self.TAG[::-1]:
            endianness = Endianness.LITTLE_ENDIAN
        else:
            raise TypeError(f'Expected {self.TAG} tag, got {tag} instead')
        self._reader = EndiannessAwareReader(self._fp, endianness)

        read_size = self._reader.read_ui32()
        if size is None:
            size = read_size
        else:
            assert read_size <= size

        self.position = position
        self.size = size

        self._parse()

    @abstractmethod
    def _parse(self):
        pass

    @property
    @abstractmethod
    def TAG(self) -> str:
        pass

    def __repr__(self):
        return f'<{self.__class__.__name__} "{self._fp.name}" @ 0x{self.position:08x}>'


class ArchiveParser(metaclass=ABCMeta):
    def __init__(self, archive: RIFXArchiveResource, reader: EndiannessAwareReader):
        self.archive = archive
        self._reader = reader

    @abstractmethod
    def parse(self):
        pass

    @property
    @abstractmethod
    def TYPES(self) -> str:
        pass


class RIFXArchiveResource(Resource):
    TAG = 'RIFX'

    PARSERS: Sequence[Type[ArchiveParser]] = tuple()

    @classmethod
    def init_parsers(cls, *parsers):
        cls.PARSERS = parsers

    def _parse(self):
        tag = self._reader.read_tag()

        for parser_class in self.PARSERS:
            if tag in parser_class.TYPES:
                parser = parser_class(self, self._reader)
                break
        else:
            raise TypeError(f'Could not find parser for a {tag} archive')

        self.content = parser.parse()
