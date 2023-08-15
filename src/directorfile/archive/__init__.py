from directorfile.archive.base import RIFXArchiveResource
from directorfile.archive.director import DirectorArchiveResource
from directorfile.archive.application import ApplicationArchiveResource

from directorfile.archive.director import load_director_archive


def _init_parsers():
    from directorfile.archive.base import RIFXArchiveResource
    from directorfile.archive.director import DirectorArchiveParser
    from directorfile.archive.shockwave import ShockwaveArchiveParser

    RIFXArchiveResource.PARSERS = [
        DirectorArchiveParser,
        ShockwaveArchiveParser
    ]


_init_parsers()
