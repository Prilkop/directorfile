from __future__ import annotations

from abc import ABCMeta, abstractmethod
from typing import BinaryIO, Optional, Sequence, Type

from directorfile.common import Endianness, EndiannessAwareReader


class Resource(metaclass=ABCMeta):
    size: int

    def load(self, fp: BinaryIO, position: int, size: Optional[int] = None) -> Resource:
        fp.seek(position)
        tag = fp.read(4).decode('ascii')

        if tag == self.TAG:
            endianness = Endianness.BIG_ENDIAN
        elif tag == self.TAG[::-1]:
            endianness = Endianness.LITTLE_ENDIAN
        else:
            raise TypeError(f'Expected {self.TAG} tag, got {tag} instead')
        reader = EndiannessAwareReader(fp, endianness)

        read_size = reader.read_ui32()
        if size is None:
            size = read_size
        else:
            assert read_size <= size

        self.size = size

        self._parse(reader, position, size)
        return self

    @abstractmethod
    def _parse(self, reader: EndiannessAwareReader, position: int, size: int):
        pass

    @property
    @abstractmethod
    def TAG(self) -> str:
        pass


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

    def _parse(self, reader: EndiannessAwareReader, position: int, size: int):
        tag = reader.read_tag()

        for parser_class in self.PARSERS:
            if tag in parser_class.TYPES:
                parser = parser_class(self, reader)
                break
        else:
            raise TypeError(f'Could not find parser for a {tag} archive')

        self.content = parser.parse()
