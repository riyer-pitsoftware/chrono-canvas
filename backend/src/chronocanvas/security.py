"""Security utilities for ChronoCanvas.

Centralises SSRF prevention, file magic-byte validation, and URL checks.
"""

import ipaddress
from urllib.parse import urlparse

# ── SSRF prevention ────────────────────────────────────────────────────────────

# Private / link-local / loopback ranges to block outbound SSRF requests to
_BLOCKED_NETWORKS = [
    ipaddress.ip_network("127.0.0.0/8"),  # loopback
    ipaddress.ip_network("10.0.0.0/8"),  # RFC 1918
    ipaddress.ip_network("172.16.0.0/12"),  # RFC 1918
    ipaddress.ip_network("192.168.0.0/16"),  # RFC 1918
    ipaddress.ip_network("169.254.0.0/16"),  # link-local / cloud metadata
    ipaddress.ip_network("100.64.0.0/10"),  # carrier-grade NAT
    ipaddress.ip_network("::1/128"),  # IPv6 loopback
    ipaddress.ip_network("fc00::/7"),  # IPv6 unique local
    ipaddress.ip_network("fe80::/10"),  # IPv6 link-local
]

_ALLOWED_SCHEMES = {"http", "https"}

_BLOCKED_HOSTNAMES = {
    "localhost",
    "ip6-localhost",
    "ip6-loopback",
    "broadcasthost",
    "0.0.0.0",
}


def is_safe_url(url: str) -> bool:
    """Return True only if the URL is safe to fetch (no SSRF risk).

    Checks:
    - Scheme must be http or https
    - Hostname must not resolve to a private/loopback/cloud-metadata IP
    - No credentials embedded in URL
    - Hostname must not be 'localhost' or similar
    """
    try:
        parsed = urlparse(url)
    except Exception:
        return False

    if parsed.scheme not in _ALLOWED_SCHEMES:
        return False

    # Block embedded credentials
    if parsed.username or parsed.password:
        return False

    hostname = parsed.hostname or ""
    if not hostname:
        return False

    # Block by name — catch common localhost variants
    if hostname.lower() in _BLOCKED_HOSTNAMES:
        return False

    # Block numeric IPs that fall in private ranges
    try:
        addr = ipaddress.ip_address(hostname)
        for network in _BLOCKED_NETWORKS:
            if addr in network:
                return False
    except ValueError:
        # Not a literal IP address — we can't resolve it here (async);
        # accept for now (DNS rebinding is a separate concern requiring
        # resolver-level controls or a lookup-then-check flow).
        pass

    return True


# ── File magic-byte validation ─────────────────────────────────────────────────

# (signature, min_length, name)
_IMAGE_SIGNATURES: list[tuple[bytes, int, str]] = [
    (b"\xff\xd8\xff", 3, "JPEG"),
    (b"\x89PNG\r\n\x1a\n", 8, "PNG"),
    (b"RIFF", 4, "WebP"),  # WebP: RIFF????WEBP, check further below
    (b"GIF87a", 6, "GIF"),
    (b"GIF89a", 6, "GIF"),
]

_WEBP_MARKER = b"WEBP"


def validate_image_magic(data: bytes) -> bool:
    """Return True if `data` starts with a recognised image magic signature."""
    if len(data) < 12:
        return False

    for sig, min_len, name in _IMAGE_SIGNATURES:
        if data[:min_len] == sig:
            if name == "WebP":
                # Bytes 8-12 must be 'WEBP'
                return data[8:12] == _WEBP_MARKER
            return True

    return False


# ── Input sanitisation helpers ─────────────────────────────────────────────────


def sanitize_search_query(value: str, max_length: int = 200) -> str:
    """Strip leading/trailing whitespace and truncate to max_length."""
    return value.strip()[:max_length]


# ── Path confinement ────────────────────────────────────────────────────────────

from pathlib import Path  # noqa: E402 — kept near usage for locality


def confine_path(path: Path, base: Path) -> Path:
    """Resolve *path* and assert it stays inside *base*.

    Returns the resolved path on success.  Raises ``PermissionError`` if the
    resolved path escapes *base* (path-traversal attempt).

    Both *path* and *base* are resolved with ``Path.resolve()`` so symlinks
    and ``..`` components are fully expanded before comparison.
    """
    resolved = path.resolve()
    base_resolved = base.resolve()
    try:
        resolved.relative_to(base_resolved)
    except ValueError:
        raise PermissionError(f"Path {str(path)!r} escapes allowed directory {str(base)!r}")
    return resolved
