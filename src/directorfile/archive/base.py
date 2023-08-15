from __future__ import annotations

from abc import ABCMeta, abstractmethod
from typing import BinaryIO, Optional, Sequence, Type

from directorfile.common import Endianness, EndiannessAwareStream, ParsingError


class Resource(metaclass=ABCMeta):
    def __repr__(self):
        return f'<{type(self).__qualname__} at {hex(id(self))}>'

    def load(self, fp: BinaryIO, position: Optional[int] = None, size: int = 0) -> Resource:
        if position is not None:
            fp.seek(position)

        reader = self.parse_tag(fp)
        data_size = reader.read_ui32()
        if size:
            assert size >= data_size
        return self.parse(reader, data_size)

    def parse(self, reader: EndiannessAwareStream, size: int) -> Resource:
        start = reader.get_current_pos()
        self._parse(reader, size)
        reader.jump(start + size)
        return self

    def parse_tag(self, fp: BinaryIO) -> EndiannessAwareStream:
        tag = fp.read(4).decode('ascii')
        if tag == self.TAG:
            endianness = Endianness.BIG_ENDIAN
        elif tag == self.TAG[::-1]:
            endianness = Endianness.LITTLE_ENDIAN
        else:
            raise ParsingError(f'Expected {self.TAG} tag, got {tag} instead')

        reader = EndiannessAwareStream(fp, endianness)
        return reader

    def save(self, fp: BinaryIO, endianness: Endianness, position: Optional[int] = None) -> int:
        if position is not None:
            fp.seek(position)

        stream = EndiannessAwareStream(fp, endianness)
        stream.skip(8)

        start = stream.get_current_pos()
        self.serialize(stream)
        size = stream.get_current_pos() - start
        stream.jump(start - 8)
        self.serialize_header(stream, size)
        stream.skip(size)

        return size

    def serialize(self, stream: EndiannessAwareStream):
        self._serialize(stream)

    def serialize_header(self, writer: EndiannessAwareStream, size: int):
        writer.write_tag(self.TAG)
        writer.write_ui32(size)

    @abstractmethod
    def _parse(self, reader: EndiannessAwareStream, size: int) -> None:
        pass

    @abstractmethod
    def _serialize(self, writer: EndiannessAwareStream) -> None:
        pass

    @property
    @abstractmethod
    def TAG(self) -> str:
        pass


class ArchiveParser(metaclass=ABCMeta):
    def __init__(self, archive: RIFXArchiveResource, reader: EndiannessAwareStream):
        self.archive = archive
        self._reader = reader

    @abstractmethod
    def parse(self):
        pass

    @property
    @abstractmethod
    def TYPES(self) -> str:
        pass


class ArchiveSerializer(metaclass=ABCMeta):
    def __init__(self, endianness: Endianness, director_version: int):
        self.endianness = endianness
        self.director_version = director_version

    def serialize(self, fp: BinaryIO, archive: RIFXArchiveResource):
        stream = EndiannessAwareStream(fp, self.endianness)
        self._serialize(stream, archive)

    @abstractmethod
    def _serialize(self, stream: EndiannessAwareStream, archive: RIFXArchiveResource):
        pass


class FileResource(Resource, metaclass=ABCMeta):
    filename: str

    def __init__(self, filename: str = ''):
        self.filename = filename

    def __repr__(self):
        if self.filename:
            identifier = f'"{self.filename}"'
        else:
            identifier = f'at {hex(id(self))}'

        return f'<{type(self).__qualname__} {identifier}>'


class RIFXArchiveResource(FileResource):
    TAG = 'RIFX'

    PARSERS: Sequence[Type[ArchiveParser]] = tuple()

    _parser: ArchiveParser

    def _parse(self, reader: EndiannessAwareStream, size: int) -> None:
        tag = reader.read_tag()

        for parser_class in self.PARSERS:
            if tag in parser_class.TYPES:
                parser = parser_class(self, reader)
                break
        else:
            raise ParsingError(f'Could not find parser for a {tag} archive')

        self._parser = parser
        parser.parse()

    def _serialize(self, writer: EndiannessAwareStream) -> None:
        raise NotImplementedError('Not directly serializable')
