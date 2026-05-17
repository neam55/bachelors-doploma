class GostParserError(Exception):
    pass


class GostPageFetchError(GostParserError):
    pass


class GostMetadataError(GostParserError):
    pass


class GostPdfDownloadError(GostParserError):
    pass


class GostPdfStructureError(GostParserError):
    pass
