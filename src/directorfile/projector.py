import os
from enum import Enum, auto
from io import SEEK_END
from struct import pack, unpack
from typing import BinaryIO

from directorfile.archive import ApplicationArchiveResource
from directorfile.common import Endianness, EndiannessAwareStream, ParsingError


class ProjectorFormat(Enum):
    WINDOWS = auto()
    MAC_OS_PEF = auto()


class Projector:
    SUPPORTED_TAGS = {'PJ01'}
    _FORMAT_DISPLAY = {
        ProjectorFormat.WINDOWS: 'Windows',
        ProjectorFormat.MAC_OS_PEF: 'Mac OS (PEF)'

    }

    executable: bytes
    application: ApplicationArchiveResource

    _filename: str
    _format: ProjectorFormat

    def __init__(self, filename: str = ''):
        self._filename = filename

    def __repr__(self):
        if self._filename:
            return f'<Projector "{self._filename}">'
        else:
            return f'<Projector at {hex(id(self))}>'

    def load(self, fp: BinaryIO):
        if hasattr(fp, 'name'):
            self._filename = os.path.abspath(fp.name)

        position = self._locate_application(fp)
        fp.seek(0)
        self.executable = fp.read(position)
        self.application = ApplicationArchiveResource().load(fp, position)

        return self

    def _locate_application(self, fp: BinaryIO):
        fp.seek(0)
        head = fp.read(0x20)
        if head[0:2] == b'MZ':
            self._format = ProjectorFormat.WINDOWS
            reader = EndiannessAwareStream(fp, Endianness.LITTLE_ENDIAN)
            fp.seek(-4, SEEK_END)
            pj_position, = unpack('<I', fp.read(4))
            if pj_position <= 0x1000 or pj_position >= fp.tell() - 0x10:
                raise ParsingError('Not a projector file')
        elif head[10:18] == b'Joy!peff':
            self._format = ProjectorFormat.MAC_OS_PEF
            reader = EndiannessAwareStream(fp, Endianness.BIG_ENDIAN)
            pj_position = 0
        else:
            raise ParsingError('Unsupported executable format')

        self._pj_position = pj_position

        reader.jump(pj_position)
        tag = reader.read_tag()
        if tag in Projector.SUPPORTED_TAGS:
            container_position = reader.read_ui32()
        else:
            raise ParsingError(f'Unsupported PJ section: {tag}')
        return container_position

    def save(self, fp: BinaryIO, endianness: Endianness):
        fp.write(self.executable)
        self.application.save(fp, endianness)

        if self._format == ProjectorFormat.WINDOWS:
            fp.write(pack('<I', self._pj_position))


def load_projector(fp: BinaryIO, name: str = ''):
    return Projector(name).load(fp)
