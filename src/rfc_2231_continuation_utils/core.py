"""Decode MIME parameter values with RFC 2231 continuation and charset encoding.

RFC 2231 extends RFC 2183 header parameters so that a single logical value can
be split across multiple header lines (continuation) and carry charset/language
information (encoding).  A raw header parser such as :func:`email.message.Message`
will hand back keys that look like ``name*0*``, ``name*1``, and
``name*0`` (quoted-printable style).  This module reassembles those fragments
into the final string the original sender intended.

Scope (chosen interpretation)
-----------------------------
RFC 2231 has three independent features: continuation (``*0``, ``*1``),
charset/language encoding (``name*=charset'lang'value``), and the
quoted-printable percent-encoding of bytes within the value.  We implement
all three together because in practice they almost always appear together —
that is the whole point of the RFC.  We deliberately do **not** implement
un-encoded continuations that carry no asterisk; the standard library already
handles plain parameters fine, and supporting that half-breed case would
require inventing a join rule the RFC leaves ambiguous.

Only the ``name*N*`` / ``name*N`` suffix forms are recognised.  Language tags
are parsed out and discarded — returning a struct would be convenient for
authors who want the language, but then every caller pays for it, so we keep
the public surface to a plain string.  Use :func:`decode_parameter_dict` when
you have a whole header as a ``dict[str, str]``; use :func:`decode_parameter`
when you already know the bare parameter name and the fragment dict.
"""

from __future__ import annotations

__all__ = ["decode_parameter", "decode_parameter_dict"]


def _parse_fragment_key(raw_key: str) -> tuple[str, int | None, bool]:
    """Split a raw key into ``(bare_name, index, encoded_flag)``.

    The encoded flag is True when the key ends with a literal ``*`` after the
    optional numeric index — that is the RFC 2231 marker meaning "this segment
    carries charset/percent-encoding".
    """
    key = raw_key.lower()
    encoded = False
    if key.endswith("*"):
        encoded = True
        key = key[:-1]

    star = key.rfind("*")
    if star == -1:
        # ``name*`` with no number — a single encoded segment, index 0.
        return key, 0 if encoded else None, encoded

    suffix = key[star + 1:]
    base = key[:star]
    if suffix.isdigit():
        return base, int(suffix), encoded

    # ``name*foo`` — not a continuation we understand.  Treat as opaque so the
    # caller's pass-through handling can deal with it.
    return raw_key.lower(), None, False


def _percent_decode_to_bytes(text: str) -> bytes:
    """Percent-decode *text* into raw bytes without applying any charset."""
    from urllib.parse import unquote_to_bytes

    return unquote_to_bytes(text)


def _decode_bytes(raw: bytes, charset: str) -> str:
    """Decode *raw* bytes using *charset*, falling back to UTF-8 on failure."""
    try:
        return raw.decode(charset)
    except (LookupError, UnicodeDecodeError):
        return raw.decode("utf-8", errors="replace")


def _parse_encoded_segment_to_bytes(value: str) -> tuple[bytes, str]:
    """Parse a ``charset'lang'percent-encoded`` segment into bytes + charset."""
    first_quote = value.find("'")
    if first_quote == -1:
        return _percent_decode_to_bytes(value), "utf-8"

    charset = value[:first_quote]
    rest = value[first_quote + 1:]
    second_quote = rest.find("'")
    if second_quote == -1:
        return _percent_decode_to_bytes(value), "utf-8"

    body = rest[second_quote + 1:]
    cs = charset.lower() or "utf-8"
    return _percent_decode_to_bytes(body), cs


def decode_parameter(name: str, fragments: dict[str, str]) -> str | None:
    """Reassemble a single RFC 2231 parameter from its *fragments*.

    *name* is the bare parameter name without any ``*N`` suffix.  *fragments*
    maps the raw keys exactly as they appeared in the header (case is
    normalised internally) to their raw string values.

    Returns the decoded string, or ``None`` when *name* has no encoded
    continuation segments in *fragments*.  Plain ``name`` values without an
    asterisk are ignored — callers who want those should read the dict
    directly.
    """
    target = name.lower()
    segments: dict[int, str] = {}
    encoded_segments: dict[int, bytes] = {}
    charset = "utf-8"

    for raw_key, raw_value in fragments.items():
        bare, index, encoded = _parse_fragment_key(raw_key)
        if bare != target:
            continue
        if index is None:
            continue
        if encoded:
            if index == 0:
                body_bytes, cs = _parse_encoded_segment_to_bytes(raw_value)
                charset = cs
                encoded_segments[index] = body_bytes
            else:
                encoded_segments[index] = _percent_decode_to_bytes(raw_value)
        else:
            # Un-encoded continuation segment (``name*N``).  RFC 2231 says these
            # are concatenated literally; we stash them but only use them when
            # no encoded form is present, which keeps the two styles from
            # colliding.
            segments.setdefault(index, raw_value)

    if encoded_segments:
        raw = b"".join(encoded_segments[i] for i in sorted(encoded_segments))
        return _decode_bytes(raw, charset)

    if not segments:
        return None

    ordered = [segments[i] for i in sorted(segments)]
    return "".join(ordered)


def decode_parameter_dict(headers: dict[str, str], name: str) -> str | None:
    """Convenience wrapper for :func:`decode_parameter` over a raw header dict.

    *headers* is the mapping produced by a MIME parser — keys may include the
    ``*N*`` suffixes.  *name* is the bare parameter name to extract.
    """
    return decode_parameter(name, headers)
