import os
import re
from io import SEEK_END
from struct import unpack
from typing import BinaryIO

from directorfile.archive.base import RIFXArchiveResource
from directorfile.common import ParsingError


class Projector:
    application: RIFXArchiveResource
    _name: str = 'UNINITIALIZED'

    def __repr__(self):
        return f'<Projector "{self._name}">'

    def _locate_application(self, fp: BinaryIO):
        fp.seek(0)
        if re.match(rb'PJ\d\d', fp.read(4)):
            container_position, = unpack('>I', fp.read(4))
        else:
            fp.seek(-4, SEEK_END)
            pj_position, = unpack('<I', fp.read(4))
            fp.seek(pj_position)
            tag = fp.read(4)
            if re.match(rb'PJ\d\d|\d\dJP', tag):
                container_position, = unpack('<I', fp.read(4))
            else:
                raise ParsingError('Could not locate a PJ section')
        return container_position

    def load(self, fp: BinaryIO):
        self._name = os.path.abspath(fp.name)
        position = self._locate_application(fp)
        self.application = RIFXArchiveResource().load(fp, position)

        return self

