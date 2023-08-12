from __future__ import annotations

import zlib
from dataclasses import dataclass
from enum import IntEnum
from typing import Dict, List, Sequence, Tuple, Type

from directorfile.archive.base import Resource
from directorfile.archive.director import DirectorArchiveParser, MMapResource, RIFXArchiveResource
from directorfile.common import EndiannessAwareReader, ParsingError


class FileType(IntEnum):
    DIRECTOR_MOVIE = 0
    DIRECTOR_CAST = 1
    XTRA = 2


@dataclass
class FileRecord:
    filename: str
    type: FileType
    resource: Resource


class DictResource(Resource):
    TAG = 'Dict'

    mapping: Dict[int, str]

    def _parse(self, reader: EndiannessAwareReader, size: int):
        values_chunk_offset = reader.read_ui32()
        values_chunk_size = reader.read_ui32()

        values_base = reader.get_current_pos() + values_chunk_offset

        reader.skip(8)
        length = reader.read_ui32()
        assert length < 0x10000  # XXX: This is here to make sure we are in the right endianness. Unsure if it's needed
        allocated_length = reader.read_ui32()
        assert allocated_length >= length
        assert reader.read_ui16() == 0x1c
        assert reader.read_ui16() == 0x08
        reader.skip(8)

        pairs = []
        for i in range(length):
            value_offset = reader.read_ui32()
            key = reader.read_ui32()
            pairs.append((key, value_offset))

        assert reader.get_current_pos() + 8 * (allocated_length - length) == values_base

        mapping = {}
        for key, value_offset in pairs:
            assert key not in mapping
            reader.jump(values_base + value_offset)
            value = reader.read_string()
            mapping[key] = value
        self.mapping = mapping


class ListResource(Resource):
    TAG = 'List'

    members: List[Tuple[int, int]]

    def _parse(self, reader: EndiannessAwareReader, size: int):
        reader.skip(8)
        length = reader.read_ui32()
        allocated_length = reader.read_ui32()
        assert allocated_length >= length
        assert reader.read_ui16() == 0x14
        assert reader.read_ui16() == 0x08

        pairs = []
        for i in range(length):
            index = reader.read_ui32()
            value = reader.read_ui32()
            pairs.append((index, value))
        self.members = pairs


class BadDResource(DictResource):
    TAG = 'BadD'


class RIFFXtraFileResource(Resource):
    TAG = 'RIFF'

    def _parse(self, reader: EndiannessAwareReader, size: int):
        assert reader.read_tag() == 'Xtra'
        assert reader.read_tag() == 'FILE'

        headered_size = reader.read_ui32()
        header_size = reader.read_ui32()
        assert header_size == 0x1c

        reader.skip(8)
        uncompressed_size = reader.read_ui32()
        reader.skip(4)
        compressed_size = reader.read_ui32()
        reader.skip(4)

        self.data = zlib.decompress(reader.read_buffer(compressed_size))

        assert len(self.data) == uncompressed_size


class ApplicationArchiveParser(DirectorArchiveParser):
    TYPES = {'APPL'}

    RESOURCE_CLASSES: Dict[str, Type[Resource]] = {
        cls.TAG: cls for cls in (
            ListResource,
            DictResource,
            BadDResource,
        )
    }

    FILE_RESOURCE_CLASSES: Sequence[Type[Resource]] = [
        RIFXArchiveResource,
        RIFFXtraFileResource
    ]

    files: List[FileRecord]

    def parse(self):
        super().parse()
        entries = self.mmap.entries

        list_entry = entries[3]
        assert list_entry.tag == 'List'
        file_list = self._fetch_resource(list_entry)
        assert isinstance(file_list, ListResource)

        dict_entry = entries[4]
        assert dict_entry.tag == 'Dict'
        filename_dict = self._fetch_resource(dict_entry)
        assert isinstance(filename_dict, DictResource)

        badd_entry = entries[5]
        assert badd_entry.tag == 'BadD'
        badd_dict = self._fetch_resource(badd_entry)
        assert isinstance(badd_dict, DictResource)

        files = []
        for i, (entry_index, file_type) in enumerate(file_list.members):
            entry = entries[entry_index]
            assert entry.tag == 'File'
            file_resource = self._fetch_resource(entry)

            filename = filename_dict.mapping[i]

            files.append(FileRecord(filename, FileType(file_type), file_resource))

        self.files = files
        self.badd = badd_dict.mapping

    def _reconstruct_resource(self, entry: MMapResource.Entry):
        fp = self._reader.fp

        tag = entry.tag
        position = entry.position
        size = entry.size

        if tag == 'File':
            for resource_class in self.FILE_RESOURCE_CLASSES:
                try:
                    return resource_class().load(fp=fp, position=position, size=size)
                except ParsingError:
                    pass
            else:
                fp.seek(position)
                raise ParsingError(f"Unknown file header: {fp.read(12)}")
        else:
            resource_class = self.RESOURCE_CLASSES.get(tag)
            if resource_class is None:
                raise ParsingError(f"Unknown resource type '{tag}'")
            return resource_class().load(fp=fp, position=position, size=size)


class ApplicationRIFXArchiveResource(RIFXArchiveResource):
    PARSERS = [ApplicationArchiveParser]

    _parser: ApplicationArchiveParser
    xtras: Dict[str, Resource]
    casts: Dict[str, Resource]
    movies: Dict[str, Resource]

    def __init__(self):
        super().__init__()
        self.xtras = {}
        self.casts = {}
        self.movies = {}

    def _parse(self, reader: EndiannessAwareReader, size: int):
        super()._parse(reader, size)
        for file_record in self._parser.files:
            files_dict = {
                FileType.XTRA: self.xtras,
                FileType.DIRECTOR_CAST: self.casts,
                FileType.DIRECTOR_MOVIE: self.movies,
            }[file_record.type]

            files_dict[file_record.filename] = file_record.resource
