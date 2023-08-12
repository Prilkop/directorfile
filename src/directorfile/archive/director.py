from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Tuple

from directorfile.archive.base import ArchiveParser, RIFXArchiveResource, Resource
from directorfile.common import EndiannessAwareReader

DIRECTOR_VERSIONS = {
    0x4c1: '5.0',
    0x4c7: '6.0',
    0x57e: '7.0',
    0x640: '8.0',
    0x708: '8.5',
    0x73a: '8.5.1',
    0x742: '10.0',
    0x744: '10.1',
    0x782: '11.5.0r593',
    0x783: '11.5.8.612',
    0x79f: '12'
}


class GenericResource(Resource):
    @property
    def TAG(self):
        return self._tag

    def __init__(self, tag: str):
        self._tag = tag

    def _parse(self, reader: EndiannessAwareReader, size: int):
        self.data = reader.read_buffer(size - 8)


class IMapResource(Resource):
    TAG = 'imap'

    mmap_position: int
    director_version: int

    def _parse(self, reader: EndiannessAwareReader, size: int):
        assert reader.read_ui32() == 0x01
        self.mmap_position = reader.read_ui32()
        self.director_version = reader.read_ui32()
        assert self.director_version in DIRECTOR_VERSIONS
        assert reader.read_i32() == 0


class MMapResource(Resource):
    TAG = 'mmap'

    entries: List["MMapResource.Entry"]

    def _parse(self, reader: EndiannessAwareReader, size: int):
        header_size = reader.read_ui16()
        assert header_size == 0x18
        width = reader.read_ui16()
        assert width == 0x14

        allocated_length = reader.read_ui32()
        length = reader.read_ui32()
        assert allocated_length >= length

        used_resources_count = reader.read_i32()
        assert reader.read_i32() == -1
        available_index = reader.read_i32()

        entries = []
        for index in range(length):
            tag = reader.read_tag()
            size = reader.read_ui32()
            position = reader.read_ui32()
            reader.skip(8)
            entries.append(MMapResource.Entry(index=index, tag=tag, size=size, position=position))

        self.entries = entries

    @dataclass
    class Entry:
        index: int
        tag: str
        size: int
        position: int

        def __repr__(self):
            return f'<Resource "{self.tag}" entry @ 0x{self.position:08x}({self.size})>'


class DirectorArchiveParser(ArchiveParser):
    TYPES = {'M!07', 'M!08', 'M!85', 'M!93', 'M!95', 'M!97', 'M*07', 'M*08', 'M*85', 'M*95', 'M*97', 'MC07',
             'MC08', 'MC85', 'MC95', 'MC97', 'MMQ5', 'MV07', 'MV08', 'MV85', 'MV93', 'MV95', 'MV97'}

    mmap: MMapResource
    _resources: Dict[Tuple[str, int], Resource]

    def __init__(self, archive: RIFXArchiveResource, reader: EndiannessAwareReader):
        super().__init__(archive, reader)
        self._resources = {}

    def _populate_fetched_resource(self, resource: Resource, position: int):
        self._resources[(resource.TAG, position)] = resource

    def _fetch_resource(self, entry: MMapResource.Entry) -> Resource:
        resource = self._resources.get((entry.tag, entry.position))
        if resource is None:
            resource = self._reconstruct_resource(entry)
            self._populate_fetched_resource(resource, entry.position)
        return resource

    def _reconstruct_resource(self, entry: MMapResource.Entry) -> Resource:
        return GenericResource(entry.tag).load(self._reader.fp, entry.position, entry.size)

    def parse(self):
        imap_position = self._reader.get_current_pos()

        imap = IMapResource().load(self._reader.fp, imap_position)
        mmap = MMapResource().load(self._reader.fp, imap.mmap_position)

        assert mmap.entries[0].tag == 'RIFX'
        self._populate_fetched_resource(self.archive, mmap.entries[0].position)

        assert mmap.entries[1].tag == 'imap'
        self._populate_fetched_resource(imap, imap_position)

        assert mmap.entries[2].tag == 'mmap'
        self._populate_fetched_resource(mmap, imap.mmap_position)

        self.mmap = mmap

        return mmap.entries[3:]
