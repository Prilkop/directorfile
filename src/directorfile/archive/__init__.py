from .base import RIFXArchiveResource


def _init_parsers():
    from .application import ApplicationArchiveParser, ListResource, DictResource, BadDResource, \
        RIFFXtraFileResource
    from .base import RIFXArchiveResource
    from .director import DirectorArchiveParser
    from .shockwave import ShockwaveArchiveParser

    RIFXArchiveResource.PARSERS = (ApplicationArchiveParser, DirectorArchiveParser, ShockwaveArchiveParser)

    ApplicationArchiveParser.RESOURCE_CLASSES = {
        cls.TAG: cls for cls in (
            ListResource,
            DictResource,
            BadDResource
        )
    }

    ApplicationArchiveParser.FILE_RESOURCE_CLASSES = [
        RIFXArchiveResource,
        RIFFXtraFileResource
    ]


_init_parsers()
