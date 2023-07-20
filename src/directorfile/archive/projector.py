import os
import re
from io import SEEK_END
from struct import unpack

from directorfile.archive.base import RIFXArchiveResource


class Projector:
    def __init__(self, filename):
        self.filename = os.path.abspath(filename)
        self._fp = open(filename, "rb")

    def __repr__(self):
        return f'<Projector "{self._fp.name}">'

    def _locate_application(self):
        self._fp.seek(0)
        if re.match(rb'PJ\d\d', self._fp.read(4)):
            container_position, = unpack('>I', self._fp.read(4))
        else:
            self._fp.seek(-4, SEEK_END)
            pj_position, = unpack('<I', self._fp.read(4))
            self._fp.seek(pj_position)
            tag = self._fp.read(4)
            if re.match(rb'PJ\d\d|\d\dJP', tag):
                container_position, = unpack('<I', self._fp.read(4))
            else:
                raise TypeError('Could not locate a PJ section')
        return container_position

    def find_application(self) -> RIFXArchiveResource:
        position = self._locate_application()
        return RIFXArchiveResource(self._fp, position)
