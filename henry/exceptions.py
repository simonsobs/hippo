class PreflightFailedError(Exception):
    pass


class InvalidSlugError(KeyError):
    pass


class ProductIncompleteError(Exception):
    pass


class CollectionIncompleteError(Exception):
    pass
