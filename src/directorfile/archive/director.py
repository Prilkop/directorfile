from __future__ import annotations

from dataclasses import dataclass
from typing import BinaryIO, Dict, List, Tuple

from directorfile.archive.base import ArchiveParser, ArchiveSerializer, RIFXArchiveResource, Resource
from directorfile.common import EndiannessAwareStream, calculate_alignment_remainder

DIRECTOR_VERSIONS = {
    0x404: '3.0',
    0x405: '3.1',
    0x45b: '4.0.0',
    0x45d: '4.0.4',
    0x4c1: '5.0',
    0x4c7: '6.0',
    0x57e: '7.0',
    0x640: '8.0',
    0x708: '8.5',
    0x73a: '8.5.1',
    0x742: '10.0',
    0x744: '10.1',
    0x781: '11.0',
    0x782: '11.5.0.593',
    0x783: '11.5.8.612',
    0x79f: '12',
}


class GenericResource(Resource):
    data: bytes

    @property
    def TAG(self):
        return self._tag

    def __init__(self, tag: str):
        super().__init__()
        self._tag = tag

    def _parse(self, reader: EndiannessAwareStream, size: int) -> None:
        self.data = reader.read_buffer(size)

    def _serialize(self, writer: EndiannessAwareStream) -> None:
        writer.write_buffer(self.data)


class IMapResource(Resource):
    TAG = 'imap'

    mmap_position: int
    director_version: int

    def __init__(self, mmap_position: int = None, director_version: int = None):
        super().__init__()
        self.mmap_position = mmap_position
        self.director_version = director_version

    def _parse(self, reader: EndiannessAwareStream, size: int) -> None:
        assert reader.read_ui32() == 1
        self.mmap_position = reader.read_ui32()
        self.director_version = reader.read_ui32()
        assert self.director_version in DIRECTOR_VERSIONS, f'Unsupported version code 0x{self.director_version:02x}'
        assert reader.read_i32() == 0

        assert reader.read_i32() == 0
        assert reader.read_i32() == 0

    def _serialize(self, writer: EndiannessAwareStream) -> None:
        writer.write_ui32(1)
        writer.write_ui32(self.mmap_position)
        writer.write_ui32(self.director_version)
        writer.write_ui32(0)

        writer.write_ui32(0)
        writer.write_ui32(0)


class MMapResource(Resource):
    TAG = 'mmap'

    entries: List["MMapResource.Entry"]

    HEADER_SIZE = 0x18
    ENTRY_WIDTH = 0x14

    def __init__(self, entries: List["MMapResource.Entry"] = None):
        super().__init__()
        if entries:
            self.entries = list(entries)
        else:
            self.entries = []

    def _parse(self, reader: EndiannessAwareStream, size: int):
        header_size = reader.read_ui16()
        assert header_size == MMapResource.HEADER_SIZE
        width = reader.read_ui16()
        assert width == MMapResource.ENTRY_WIDTH

        allocated_length = reader.read_ui32()
        length = reader.read_ui32()
        assert allocated_length >= length

        # TODO: support free amd junk indices
        unk_junk_indices = [reader.read_i32(), reader.read_i32()]
        unk_free_index = reader.read_i32()

        entries = []
        for index in range(length):
            tag = reader.read_tag()
            size = reader.read_ui32()
            position = reader.read_ui32()

            reader.skip(8)

            entries.append(MMapResource.Entry(index=index, tag=tag, position=position, size=size))

        assert all(index == -1 or entries[index].tag == 'junk' for index in unk_junk_indices)
        assert unk_free_index == -1 or entries[unk_free_index].tag == 'free'

        self.entries = entries

    def _serialize(self, writer: EndiannessAwareStream) -> None:
        writer.write_ui16(MMapResource.HEADER_SIZE)
        writer.write_ui16(MMapResource.ENTRY_WIDTH)

        writer.write_ui32(len(self.entries))
        writer.write_ui32(len(self.entries))

        # TODO: support free amd junk indices
        writer.write_i32(-1)
        writer.write_i32(-1)
        writer.write_i32(-1)

        for entry in self.entries:
            writer.write_tag(entry.tag)
            writer.write_ui32(entry.size)
            writer.write_ui32(entry.position)

            # TODO: support type-specific entry fields
            writer.write_ui32(0)
            writer.write_ui32(0)

    @staticmethod
    def calculate_needed_size(length):
        return MMapResource.HEADER_SIZE + length * MMapResource.ENTRY_WIDTH

    @dataclass
    class Entry:
        index: int
        tag: str
        position: int
        size: int

        def __repr__(self):
            return f'<Resource "{self.tag}" entry @ 0x{self.position:08x}({self.size})>'


class DirectorArchiveParser(ArchiveParser):
    TYPES = {'M!07', 'M!08', 'M!85', 'M!93', 'M!95', 'M!97', 'M*07', 'M*08', 'M*85', 'M*95', 'M*97', 'MC07',
             'MC08', 'MC85', 'MC95', 'MC97', 'MMQ5', 'MV07', 'MV08', 'MV85', 'MV93', 'MV95', 'MV97'}

    _mmap: MMapResource

    director_version: int
    entries: List[Tuple[MMapResource.Entry, Resource]]

    _resources: Dict[Tuple[str, int], Resource]

    def __init__(self, archive: RIFXArchiveResource, reader: EndiannessAwareStream):
        super().__init__(archive, reader)
        self.entries = []
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

        self._mmap = mmap

        self.director_version = imap.director_version
        self.entries = [(entry, self._fetch_resource(entry))
                        for entry in mmap.entries[3:]
                        if entry.tag not in ('free', 'junk')]


class DirectorArchiveSerializer(ArchiveSerializer):
    def _serialize(self, stream: EndiannessAwareStream, archive: DirectorArchiveResource):
        self._serialize_resources(stream, 'MV93', archive.resources)

    def _serialize_resources(self, stream: EndiannessAwareStream, archive_type: str, resources: Dict[int, Resource]):
        archive_position = stream.get_current_pos() - 8
        imap_position = archive_position + 12
        mmap_position = imap_position + 8 + 0x18
        mmap_size = MMapResource.calculate_needed_size(max(resources.keys()) + 1)
        resources_offset = mmap_position + 8 + mmap_size
        stream.jump(resources_offset)

        entries = self._generate_entries(stream, resources)
        archive_size = max(entry.position + entry.size + 8 for entry in entries) - archive_position - 8

        entries = [
                      MMapResource.Entry(index=0, tag='RIFX', position=archive_position, size=archive_size),
                      MMapResource.Entry(index=1, tag='imap', position=imap_position, size=0x18),
                      MMapResource.Entry(index=2, tag='mmap', position=mmap_position, size=mmap_size),
                  ] + entries

        MMapResource(entries).save(stream.fp, stream.endianness, mmap_position)
        IMapResource(mmap_position, self.director_version).save(stream.fp, stream.endianness, imap_position)
        stream.jump(archive_position + 8)
        stream.write_tag(archive_type)
        stream.jump(archive_position + 8 + archive_size)

    def _generate_entries(self, stream: EndiannessAwareStream, resources: Dict[int, Resource]):
        entry_dict = {}
        for index, resource in resources.items():
            if index < 3:
                continue

            # 16-bit alignment (critical for Xtra file loading)
            stream.skip(calculate_alignment_remainder(stream.get_current_pos(), 2))

            position = stream.get_current_pos()
            size = resource.save(stream.fp, stream.endianness)
            entry_dict[index] = MMapResource.Entry(index=index, tag=resource.TAG, position=position, size=size)

        entries = [
            entry_dict.get(index) or MMapResource.Entry(index, 'free', 0, 0)
            for index in range(3, max(entry_dict.keys()) + 1)
        ]
        return entries


class DirectorArchiveResource(RIFXArchiveResource):
    _parser: DirectorArchiveParser

    resources: Dict[int, Resource]
    director_version: int

    def __init__(self, resources: Dict[int, Resource] = None, director_version: int = None):
        super().__init__()
        if not resources:
            self.resources = {}
        else:
            self.resources = resources

        self.director_version = director_version

    def _parse(self, reader: EndiannessAwareStream, size: int):
        super()._parse(reader, size)

        self.director_version = self._parser.director_version

        for entry, resource in self._parser.entries:
            if entry.tag not in ('free', 'junk', '\x00\x00\x00\x00'):
                self.resources[entry.index] = resource

    def _serialize(self, writer: EndiannessAwareStream) -> None:
        serializer = DirectorArchiveSerializer(writer.endianness, self.director_version)
        serializer.serialize(writer.fp, self)


def load_director_archive(fp: BinaryIO):
    return DirectorArchiveResource().load(fp)
