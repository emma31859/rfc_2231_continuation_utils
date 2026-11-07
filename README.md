# rfc_2231_continuation_utils

Decodes MIME parameter values that use RFC 2231 continuation segments and
charset/percent encoding, turning the fragment keys a raw header parser hands
you back into the single string the sender wrote.

```python
from rfc_2231_continuation_utils import decode_parameter_dict

raw = {
    "filename*0*": "utf-8''café",
    "filename*1*": "%20report.pdf",
}
print(decode_parameter_dict(raw, "filename"))  # café report.pdf
```

## Why this exists

A generic MIME header parser breaks ``Content-Disposition`` parameters into a
flat dict whose keys carry the RFC 2231 suffixes verbatim — ``filename*0*``,
``filename*1*``, and so on.  Reassembling those fragments, applying the charset
from the first segment, and percent-decoding the bytes is fiddly and
repeatedly reimplemented.  This library does that one job and nothing else.

The trade-off: the public API returns a plain string.  Language tags are
parsed and discarded.  If you need the language you will want a different
library; returning a struct would tax every caller for information most do not
use.

## Edge you will hit

The library only recognises the ``name*N*`` / ``name*N`` continuation forms.
A bare ``name`` key (no asterisk, no number) is passed through untouched — we
assume the caller reads plain parameters directly from their header dict.
Continuation indexes are compared numerically, so ``name*10*`` correctly sorts
after ``name*2*``.

## Performance

The window keeps a bounded buffer, so `push` is constant time and memory does not
grow with the length of the stream. `peak` and `trough` are linear in the window
size, which is the trade that keeps `push` cheap.

