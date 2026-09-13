"""
Body formatting helpers for queued outreach messages.

Email clients wrap text to the reader's own window. A body that also carries
hard newlines mid-sentence renders as ragged breaks at every width except the
author's, which is a common failure mode when copy is drafted in a rich text editor.

Queue bodies are stored one line per paragraph, blank line between paragraphs.
`unwrap_body` restores that shape for copy that was written fill-wrapped.
"""

import re

# A "fill-wrapped" paragraph is a run of lines all broken near the same column.
WRAP_MIN = 45     # shorter than this and the break was the author's intent
WRAP_MAX = 90     # longer and the author wasn't filling to a column at all
WRAP_SPREAD = 20  # allowed variation across a filled run's non-final lines

# Lines that carry their own structure are never joined into a neighbour.
MARKER = re.compile(r"^\s*([-*•>]|\d+[.)])\s")

# Trailing quotes and brackets sit outside the punctuation that ends a sentence.
CLOSERS = "\"'’”)]"
TERMINATORS = ".?!"


def _ends_a_sentence(line: str) -> bool:
    return line.rstrip().rstrip(CLOSERS).endswith(tuple(TERMINATORS))


def _is_fill_wrapped(block: list[str]) -> bool:
    """True when a run of lines looks machine-filled rather than deliberate."""
    if len(block) < 2:
        return False
    if any(MARKER.match(line) for line in block):
        return False

    lengths = [len(line) for line in block[:-1]]
    if not all(WRAP_MIN <= n <= WRAP_MAX for n in lengths):
        return False
    if max(lengths) - min(lengths) > WRAP_SPREAD:
        return False

    # A machine break lands mid-sentence. A line that closes its sentence and
    # is followed by another line was broken there on purpose — a sign-off, a
    # closing line — so leave the whole run as the author set it.
    if any(_ends_a_sentence(line) for line in block[:-1]):
        return False

    return len(block[-1]) <= WRAP_MAX


def unwrap_body(text: str) -> str:
    """Join hard-wrapped prose back into one line per paragraph.

    Runs that aren't fill-wrapped prose — signatures, list items, LinkedIn
    notes already written as single lines — are returned exactly as given.
    """
    out: list[str] = []
    block: list[str] = []

    def flush() -> None:
        if not block:
            return
        out.append(" ".join(line.strip() for line in block) if _is_fill_wrapped(block) else "\n".join(block))
        block.clear()

    for line in text.split("\n"):
        if line.strip():
            block.append(line.rstrip())
        else:
            flush()
            out.append("")
    flush()

    return "\n".join(out)
