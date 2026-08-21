"""Conservative deterministic product-text normalization."""

import unicodedata


def normalize_product_text(value: str) -> str:
    if type(value) is not str:
        raise TypeError("product text must be an exact string")
    return " ".join(unicodedata.normalize("NFKC", value).split()).casefold()
