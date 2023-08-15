from __future__ import annotations

import zlib
from dataclasses import dataclass
from enum import IntEnum
from typing import BinaryIO, Dict, List, Optional, Sequence, Tuple, Type

from directorfile.archive.base import Resource
from directorfile.archive.director import DirectorArchiveParser, DirectorArchiveResource, DirectorArchiveSerializer, \
    MMapResource, RIFXArchiveResource
from directorfile.common import Endianness, EndiannessAwareStream, ParsingError, calculate_alignment_remainder


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

    HEADER_SIZE = 0x1c
    ENTRY_WIDTH = 0x08

    mapping: Dict[int, str]

    def __init__(self, mapping: Dict[int, str] = None):
        super().__init__()

        if not mapping:
            self.mapping = {}
        else:
            self.mapping = dict(mapping)

    def _parse(self, reader: EndiannessAwareStream, size: int):
        values_chunk_offset = reader.read_ui32()
        values_chunk_size = reader.read_ui32()

        header_offset = reader.get_current_pos()
        values_base = header_offset + values_chunk_offset

        assert reader.read_ui32() == 0
        assert reader.read_ui32() == 0

        length = reader.read_ui32()
        allocated_length = reader.read_ui32()
        assert allocated_length >= length

        assert reader.read_ui16() == DictResource.HEADER_SIZE
        assert reader.read_ui16() == DictResource.ENTRY_WIDTH

        assert reader.read_ui32() == 0
        assert reader.read_ui32() == 0

        pairs = []
        for i in range(length):
            value_offset = reader.read_ui32()
            key = reader.read_ui32()
            pairs.append((key, value_offset))

        reader.skip(8 * (allocated_length - length))
        assert reader.get_current_pos() == values_base

        assert reader.read_ui32() == 0
        assert reader.read_ui32() == 0

        values_chunk_used = reader.read_ui32()
        assert values_chunk_used <= values_chunk_size

        assert reader.read_ui32() == values_chunk_size
        assert reader.read_ui32() == 20

        mapping = {}
        for key, value_offset in pairs:
            assert key not in mapping
            reader.jump(values_base + value_offset)
            value = reader.read_string()
            mapping[key] = value
        self.mapping = mapping

    def _serialize(self, writer: EndiannessAwareStream) -> None:
        values_chunk_offset = DictResource.HEADER_SIZE + len(self.mapping) * DictResource.ENTRY_WIDTH

        values_chunk_used = 20
        for value in self.mapping.values():
            values_chunk_used += 4 + len(value)
            values_chunk_used += calculate_alignment_remainder(len(value), 4)
        values_chunk_size = values_chunk_used

        writer.write_ui32(values_chunk_offset)
        writer.write_ui32(values_chunk_used)

        header_base = writer.get_current_pos()

        writer.write_ui32(0)
        writer.write_ui32(0)

        writer.write_ui32(len(self.mapping))
        writer.write_ui32(len(self.mapping))

        writer.write_ui16(DictResource.HEADER_SIZE)
        writer.write_ui16(DictResource.ENTRY_WIDTH)

        writer.write_ui32(0)
        writer.write_ui32(0)

        value_offset = 20
        for key, value in self.mapping.items():
            writer.write_ui32(value_offset)
            writer.write_ui32(key)

            value_offset += 4 + len(value)
            value_offset += calculate_alignment_remainder(len(value), 4)

        values_base = writer.get_current_pos()
        assert values_base - header_base == values_chunk_offset

        writer.write_ui32(0)
        writer.write_ui32(0)
        writer.write_ui32(values_chunk_used)
        writer.write_ui32(values_chunk_size)
        writer.write_ui32(20)

        for key, value in self.mapping.items():
            writer.write_string(value)
            # 32-bit alignment
            writer.skip(calculate_alignment_remainder(len(value), 4))

        assert values_chunk_used == writer.get_current_pos() - values_base


class ListResource(Resource):
    TAG = 'List'

    HEADER_SIZE = 0x14
    ENTRY_WIDTH = 0x08

    members: List[Tuple[int, int]]

    def __init__(self, members: List[Tuple[int, int]] = None):
        super().__init__()

        if not members:
            self.members = []
        else:
            self.members = list(members)

    def _parse(self, reader: EndiannessAwareStream, size: int):
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

    def _serialize(self, writer: EndiannessAwareStream) -> None:
        writer.write_ui32(0)
        writer.write_ui32(0)

        writer.write_ui32(len(self.members))
        writer.write_ui32(len(self.members))

        writer.write_ui16(ListResource.HEADER_SIZE)
        writer.write_ui16(ListResource.ENTRY_WIDTH)

        for index, value in self.members:
            writer.write_ui32(index)
            writer.write_ui32(value)


class BadDResource(DictResource):
    TAG = 'BadD'


class RIFFXtraFileResource(Resource):
    TAG = 'RIFF'

    HEADER_SIZE = 0x1c

    def _parse(self, reader: EndiannessAwareStream, size: int):
        assert reader.read_tag() == 'Xtra'
        assert reader.read_tag() == 'FILE'

        headered_size = reader.read_ui32()
        header_size = reader.read_ui32()
        assert header_size == RIFFXtraFileResource.HEADER_SIZE

        reader.skip(8)
        uncompressed_size = reader.read_ui32()
        reader.skip(4)
        compressed_size = reader.read_ui32()
        reader.skip(4)

        assert headered_size == compressed_size + header_size

        self.data = zlib.decompress(reader.read_buffer(compressed_size))

        assert len(self.data) == uncompressed_size

    def save(self, fp: BinaryIO, endianness: Endianness, position: Optional[int] = None) -> int:
        return super().save(fp, Endianness.BIG_ENDIAN, position)

    def _serialize(self, writer: EndiannessAwareStream) -> None:
        writer.write_tag('Xtra')
        writer.write_tag('FILE')

        compressed_data = zlib.compress(self.data)

        writer.write_ui32(len(compressed_data) + RIFFXtraFileResource.HEADER_SIZE)
        writer.write_ui32(RIFFXtraFileResource.HEADER_SIZE)

        writer.write_ui32(0)
        writer.write_ui32(0)
        writer.write_ui32(len(self.data))
        writer.write_ui32(0)
        writer.write_ui32(len(compressed_data))
        writer.write_ui32(0)

        writer.write_buffer(compressed_data)


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
        DirectorArchiveResource,
        RIFFXtraFileResource
    ]

    files: List[FileRecord]
    badd: Dict

    def parse(self):
        super().parse()
        entries = self._mmap.entries

        list_entry = entries[3]
        assert list_entry.tag == 'List'
        file_type_list = self._fetch_resource(list_entry)
        assert isinstance(file_type_list, ListResource)

        dict_entry = entries[4]
        assert dict_entry.tag == 'Dict'
        filename_dict = self._fetch_resource(dict_entry)
        assert isinstance(filename_dict, DictResource)

        badd_entry = entries[5]
        assert badd_entry.tag == 'BadD'
        badd_dict = self._fetch_resource(badd_entry)
        assert isinstance(badd_dict, DictResource)

        files = []
        for i, (entry_index, file_type) in enumerate(file_type_list.members):
            entry = entries[entry_index]

            assert entry.tag == 'File'

            filename = filename_dict.mapping[i]

            file_resource = self._fetch_resource(entry)

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


class ApplicationArchiveSerializer(DirectorArchiveSerializer):

    def _serialize(self, stream: EndiannessAwareStream, archive: ApplicationArchiveResource):
        xtras_first_index = 6
        movies_first_index = xtras_first_index + len(archive.xtras)
        casts_first_index = movies_first_index + len(archive.movies)

        files = [
            *(
                (xtras_first_index + index, FileType.XTRA, path, resource)
                for index, (path, resource) in enumerate(archive.xtras.items())
            ),
            *(
                (movies_first_index + index, FileType.DIRECTOR_MOVIE, path, resource)
                for index, (path, resource) in enumerate(archive.movies.items())
            ),
            *(
                (casts_first_index + index, FileType.DIRECTOR_CAST, path, resource)
                for index, (path, resource) in enumerate(archive.casts.items())
            ),
        ]

        file_type_list = ListResource([(index, file_type) for index, file_type, path, resource in files])
        filename_dict = DictResource({i: path for i, (index, file_type, path, resource) in enumerate(files)})
        badd_dict = BadDResource(archive.badd)

        resources = {
            3: file_type_list,
            4: filename_dict,
            5: badd_dict,
            **{index: resource for index, file_type, path, resource in files}
        }

        self._serialize_resources(stream, 'APPL', resources)

    def _generate_entries(self, stream, resources):
        entries = super()._generate_entries(stream, resources)
        for entry in entries:
            if entry.tag in ('RIFF', 'RIFX'):
                entry.tag = 'File'
                entry.size += 8
        return entries


class ApplicationArchiveResource(RIFXArchiveResource):
    PARSERS = [ApplicationArchiveParser]

    _parser: ApplicationArchiveParser
    xtras: Dict[str, Resource]
    casts: Dict[str, Resource]
    movies: Dict[str, Resource]

    badd: Dict[int, str]
    director_version: int

    def __init__(self):
        super().__init__()
        self.xtras = {}
        self.casts = {}
        self.movies = {}

    def _parse(self, reader: EndiannessAwareStream, size: int) -> None:
        super()._parse(reader, size)
        for file_record in self._parser.files:
            files_dict = {
                FileType.XTRA: self.xtras,
                FileType.DIRECTOR_CAST: self.casts,
                FileType.DIRECTOR_MOVIE: self.movies,
            }[file_record.type]

            files_dict[file_record.filename] = file_record.resource

        self.badd = self._parser.badd

        self.director_version = self._parser.director_version

    def _serialize(self, writer: EndiannessAwareStream) -> None:
        serializer = ApplicationArchiveSerializer(writer.endianness, self.director_version)
        serializer.serialize(writer.fp, self)
