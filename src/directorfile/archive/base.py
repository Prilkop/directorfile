from __future__ import annotations

from abc import ABCMeta, abstractmethod
from typing import BinaryIO, Optional, Sequence, Type

from directorfile.common import Endianness, EndiannessAwareReader, ParsingError


class Resource(metaclass=ABCMeta):
    size: int

    def __init__(self):
        self.size = 0

    def load(self, fp: BinaryIO, position: Optional[int] = None, size: int = 0) -> Resource:
        if position is not None:
            fp.seek(position)

        reader = self.parse_header(fp)
        return self.parse(reader, size)

    def parse(self, reader: EndiannessAwareReader, size: int) -> Resource:
        start = reader.get_current_pos()
        if size:
            if self.size:
                assert self.size <= size
            else:
                self.size = size

        self._parse(reader, self.size)
        reader.jump(start + self.size)
        return self

    def parse_header(self, fp: BinaryIO) -> EndiannessAwareReader:
        tag = fp.read(4).decode('ascii')
        if tag == self.TAG:
            endianness = Endianness.BIG_ENDIAN
        elif tag == self.TAG[::-1]:
            endianness = Endianness.LITTLE_ENDIAN
        else:
            raise ParsingError(f'Expected {self.TAG} tag, got {tag} instead')

        reader = EndiannessAwareReader(fp, endianness)
        self.size = reader.read_ui32()

        return reader

    @abstractmethod
    def _parse(self, reader: EndiannessAwareReader, size: int) -> None:
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

    _parser: ArchiveParser

    def _parse(self, reader: EndiannessAwareReader, size: int):
        tag = reader.read_tag()

        for parser_class in self.PARSERS:
            if tag in parser_class.TYPES:
                parser = parser_class(self, reader)
                break
        else:
            raise ParsingError(f'Could not find parser for a {tag} archive')

        self._parser = parser
        parser.parse()
