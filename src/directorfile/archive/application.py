from __future__ import annotations

import zlib
from typing import Dict, List, Sequence, Tuple, Type

from directorfile.archive.base import Resource
from directorfile.archive.director import DirectorArchiveParser, MMapResource


class DictResource(Resource):
    TAG = 'Dict'

    mapping: Dict[int, str]

    def _parse(self):
        values_chunk_offset = self._reader.read_ui32()
        values_chunk_size = self._reader.read_ui32()

        values_base = self.position + 8 + values_chunk_offset + 8

        self._reader.skip(8)
        length = self._reader.read_ui32()
        assert length < 0x10000  # XXX: This is here to make sure we are in the right endianness. Unsure if it's needed
        assert self._reader.read_ui32() == length
        assert self._reader.read_ui16() == 0x1c
        assert self._reader.read_ui16() == 0x08
        self._reader.skip(8)

        pairs = []
        for i in range(length):
            value_offset = self._reader.read_ui32()
            key = self._reader.read_ui32()
            pairs.append((key, value_offset))

        assert self._reader.get_current_pos() == values_base

        mapping = {}
        for key, value_offset in pairs:
            assert key not in mapping
            self._reader.jump(values_base + value_offset)
            value = self._reader.read_string()
            mapping[key] = value
        self.mapping = mapping


class ListResource(Resource):
    TAG = 'List'

    def _parse(self):
        pass


class BadDResource(Resource):
    TAG = 'BadD'

    def _parse(self):
        pass


class RIFFXtraFileResource(Resource):
    TAG = 'RIFF'

    def _parse(self):
        assert self._reader.read_tag() == 'Xtra'
        assert self._reader.read_tag() == 'FILE'

        headered_size = self._reader.read_ui32()
        header_size = self._reader.read_ui32()
        assert header_size == 0x1c

        self._reader.skip(8)
        uncompressed_size = self._reader.read_ui32()
        self._reader.skip(4)
        compressed_size = self._reader.read_ui32()
        self._reader.skip(4)

        self.data = zlib.decompress(self._reader.read_buffer(compressed_size))

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
                    return resource_class(fp, position, size)
                except TypeError:
                    pass
            else:
                fp.seek(position)
                raise TypeError(f"Unknown file header: {fp.read(12)}")
        else:
            resource_class = self.RESOURCE_CLASSES.get(tag)
            if resource_class is None:
                raise TypeError(f"Unknown resource type '{tag}'")
            return resource_class(fp=fp, position=position, size=size)
