from .application import ApplicationRIFXArchiveResource
from .base import RIFXArchiveResource


def _init_parsers():
    from .base import RIFXArchiveResource
    from .director import DirectorArchiveParser
    from .shockwave import ShockwaveArchiveParser

    RIFXArchiveResource.PARSERS = [
        DirectorArchiveParser,
        ShockwaveArchiveParser
    ]


_init_parsers()
