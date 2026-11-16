"""Validated cover resolution with ISBN fallback and optional local originals."""
import base64
import hashlib
from collections import deque
from threading import Lock
from time import monotonic
from io import BytesIO
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit, parse_qsl, urlencode
from urllib.request import urlopen, Request
from PIL import Image
import streamlit as st

# Google Books returns these error graphics with HTTP 200.
UNAVAILABLE_HASHES = {
 '3efa8c43e5b4348f303a528c81adf435f0111ea752fe9f0f6241478b60987fa6',
 '12557f8948b8bdc6af436e3a8b3adddd45f7f7d2b67c5832e799cdf4686f72bb',
}
LOCAL_COVERS = Path(__file__).resolve().parents[2] / 'data' / 'covers'
_alternative_requests = deque()
_alternative_lock = Lock()


def allow_alternative_request():
    # Open Library permits 100 ISBN requests per IP per five minutes.
    with _alternative_lock:
        now = monotonic()
        while _alternative_requests and now - _alternative_requests[0] >= 300:
            _alternative_requests.popleft()
        if len(_alternative_requests) >= 90:
            return False
        _alternative_requests.append(now)
        return True


def validate_image(data, minimum_width=300):
    if len(data) > 5_000_000 or hashlib.sha256(data).hexdigest() in UNAVAILABLE_HASHES:
        raise ValueError('Unavailable cover')
    with Image.open(BytesIO(data)) as image:
        width, height = image.size
        mime = Image.MIME.get(image.format)
        image.verify()
    if not mime or width < minimum_width or not .35 <= width / height <= 1.25:
        raise ValueError('Insufficient cover resolution or invalid proportions')
    return mime, width


def download(url):
    with urlopen(Request(url, headers={'User-Agent':'SpaceBooks/1.0 (book cover display)'}), timeout=3) as response:
        return response.read(5_000_001)


@st.cache_data(ttl=21600, max_entries=1024, show_spinner=False)
def cover_image(isbn, thumbnail, allow_alternative=True):
    """Return (verified image URL, high_resolution); never invent a cover."""
    if not isbn.isdigit() or len(isbn) not in (10, 13):
        return None, False
    for ext in ('jpg','jpeg','png','webp'):
        path = LOCAL_COVERS / f'{isbn}.{ext}'
        if path.is_file():
            try:
                data = path.read_bytes()
                mime, _ = validate_image(data)
                return f'data:{mime};base64,' + base64.b64encode(data).decode('ascii'), True
            except (OSError, ValueError):
                continue
    parts = urlsplit(thumbnail or '')
    candidates = []
    if parts.hostname in ('books.google.com','books.google.com.br'):
        params = dict(parse_qsl(parts.query))
        params['zoom'] = '3'
        candidates.append(urlunsplit(('https',parts.netloc,parts.path,urlencode(params),'')))
    elif parts.scheme == 'https':
        candidates.append(thumbnail)
    for url in candidates:
        try:
            data = download(url)
            mime, _ = validate_image(data)
            return f'data:{mime};base64,' + base64.b64encode(data).decode('ascii'), True
        except (OSError, ValueError):
            pass
    # Only requested for a product being viewed; no bulk crawl of Open Library.
    if allow_alternative and allow_alternative_request():
        alternative = f'https://covers.openlibrary.org/b/isbn/{isbn}-L.jpg?default=false'
        try:
            data = download(alternative)
            validate_image(data)
            return alternative, True
        except (OSError, ValueError):
            pass
    if thumbnail:
        try:
            data = download(thumbnail.replace('http://','https://',1))
            mime, _ = validate_image(data, minimum_width=100)
            return f'data:{mime};base64,' + base64.b64encode(data).decode('ascii'), False
        except (OSError, ValueError):
            pass
    return None, False
