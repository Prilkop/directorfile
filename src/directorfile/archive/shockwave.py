from directorfile.archive.base import ArchiveParser


class ShockwaveArchiveParser(ArchiveParser):
    TYPES = {'FGDC', 'FGDM'}

    def parse(self):
        raise NotImplementedError("Shockwave archives are not yet supported")
