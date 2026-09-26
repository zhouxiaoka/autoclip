"""HTTP Content-Disposition values that survive latin-1 header encoding."""

from urllib.parse import quote

_DISPOSITIONS = {"inline", "attachment"}


def content_disposition_header(filename: str, disposition: str = "attachment") -> str:
    """Build an ASCII Content-Disposition header for a possibly non-ASCII filename.

    Starlette encodes response header values as latin-1. A raw title such as
    ``切片.mp4`` in ``Content-Disposition`` raises ``UnicodeEncodeError`` and
    the preview/download request 500s. RFC 5987 ``filename*`` percent-encodes
    the UTF-8 name so the header stays ASCII. Matches the clip download
    endpoint (``filename*=UTF-8''``).
    """
    kind = disposition if disposition in _DISPOSITIONS else "attachment"
    # ``replace`` keeps undecodable filesystem surrogates from raising here.
    encoded = quote(filename.encode("utf-8", "replace"))
    return f"{kind}; filename*=UTF-8''{encoded}"
