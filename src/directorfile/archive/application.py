from __future__ import annotations

import zlib
from typing import Dict, List, Sequence, Tuple, Type

from directorfile.archive.base import Resource
from directorfile.archive.director import DirectorArchiveParser, MMapResource
from directorfile.common import EndiannessAwareReader


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
        assert reader.read_ui32() == length
        assert reader.read_ui16() == 0x1c
        assert reader.read_ui16() == 0x08
        reader.skip(8)

        pairs = []
        for i in range(length):
            value_offset = reader.read_ui32()
            key = reader.read_ui32()
            pairs.append((key, value_offset))

        assert reader.get_current_pos() == values_base

        mapping = {}
        for key, value_offset in pairs:
            assert key not in mapping
            reader.jump(values_base + value_offset)
            value = reader.read_string()
            mapping[key] = value
        self.mapping = mapping


class ListResource(Resource):
    TAG = 'List'

    def _parse(self, reader: EndiannessAwareReader, size: int):
        pass


class BadDResource(Resource):
    TAG = 'BadD'

    def _parse(self, reader: EndiannessAwareReader, size: int):
        pass


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

    RESOURCE_CLASSES: Dict[str, Type[Resource]]
    FILE_RESOURCE_CLASSES: Sequence[Type[Resource]]

    files: List[Tuple[str, Resource]]

    def parse(self):
        entries = super().parse()
        assert entries[0].tag == 'List'

        assert entries[1].tag == 'Dict'
        filename_dict = self._fetch_resource(entries[1])
        assert isinstance(filename_dict, DictResource)

        assert entries[2].tag == 'BadD'

        file_entries = entries[3:]
        assert all(entry.tag == 'File' for entry in file_entries)

        return [
            (filename_dict.mapping[index], self._fetch_resource(entry))
            for index, entry in enumerate(file_entries)
        ]

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
