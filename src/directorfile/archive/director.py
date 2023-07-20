from __future__ import annotations

from dataclasses import dataclass
from typing import BinaryIO, Dict, Optional, Tuple

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

    def __init__(self, tag: str, fp: BinaryIO, position: int, size: Optional[int] = None):
        self._tag = tag
        super().__init__(fp, position, size)

    def _parse(self):
        self.data = self._reader.read_buffer(self.size - 8)


class IMapResource(Resource):
    TAG = 'imap'

    mmap_position: int
    director_version: int

    def _parse(self):
        assert self._reader.read_ui32() == 0x01
        self.mmap_position = self._reader.read_ui32()
        self.director_version = self._reader.read_ui32()
        assert self.director_version in DIRECTOR_VERSIONS
        assert self._reader.read_i32() == 0


class MMapResource(Resource):
    TAG = 'mmap'

    def __init__(self, fp: BinaryIO, position: int):
        super().__init__(fp, position)

    def _parse(self):
        header_size = self._reader.read_ui16()
        assert header_size == 0x18
        width = self._reader.read_ui16()
        assert width == 0x14

        allocated_length = self._reader.read_ui32()
        length = self._reader.read_ui32()
        assert allocated_length >= length

        used_resources_count = self._reader.read_i32()
        assert self._reader.read_i32() == -1
        available_index = self._reader.read_i32()

        entries = []
        for i in range(length):
            entry_position = self._reader.get_current_pos()
            tag = self._reader.read_tag()
            size = self._reader.read_ui32()
            position = self._reader.read_ui32()
            self._reader.skip(8)
            entries.append(MMapResource.Entry(entry_position=entry_position,
                                              tag=tag, size=size, position=position))

        self.entries = entries

    @dataclass
    class Entry:
        entry_position: int
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

    def _populate_fetched_resource(self, resource: Resource):
        self._resources[(resource.TAG, resource.position)] = resource

    def _fetch_resource(self, entry: MMapResource.Entry) -> Resource:
        resource = self._resources.get((entry.tag, entry.position))
        if resource is None:
            resource = self._reconstruct_resource(entry)
            self._populate_fetched_resource(resource)
        return resource

    def _reconstruct_resource(self, entry: MMapResource.Entry) -> Resource:
        return GenericResource(entry.tag, self._reader.fp, entry.position, entry.size)

    def parse(self):
        imap = IMapResource(self._reader.fp, self._reader.get_current_pos())

        mmap = MMapResource(self._reader.fp, imap.mmap_position)

        self._populate_fetched_resource(self.archive)
        self._populate_fetched_resource(imap)
        self._populate_fetched_resource(mmap)

        self.mmap = mmap

        assert mmap.entries[0].tag == 'RIFX'
        assert mmap.entries[1].tag == 'imap'
        assert mmap.entries[2].tag == 'mmap'

        return mmap.entries[3:]
