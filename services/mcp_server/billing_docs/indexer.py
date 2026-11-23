"""Split the Billing Guide into section chunks and search them with BM25 (full-text, no embeddings).

Chunking: one chunk per numbered `###` subsection (e.g. 3.2). A numbered `##` section with no
subsections (sections 1 and 9) is a single chunk. The document preamble is not indexed.
Each chunk keeps its section ID, heading and parent heading so results can cite their source.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

from rank_bm25 import BM25Okapi

DEFAULT_GUIDE = Path(__file__).resolve().parent.parent / "data" / "Mobile_Provider_Billing_Guide.md"

_SECTION = re.compile(r"^##\s+(\d+)\.\s+(.+?)\s*$")
_SUBSECTION = re.compile(r"^###\s+(\d+\.\d+)\s+(.+?)\s*$")
_DOC_ID = re.compile(r"\*\*Document ID:\*\*\s*(\S+)")
_TOKEN = re.compile(r"[a-z0-9]+")

# Small English stopword list: keeps BM25 focused on billing terms.
STOPWORDS = frozenset(
    """a an and are as at be been but by can do does for from has have how i if in is it its my
    of on or our so than that the their then there this to was what when which who why will with
    you your me much""".split()
)


@dataclass(frozen=True)
class Chunk:
    section: str          # "3.2"
    heading: str          # "Additional internet blocks"
    parent_heading: str   # "Internet pricing"
    text: str             # plain text, markdown emphasis removed


def _stem(token: str) -> str:
    """Very light suffix stripping so 'payments'/'paying'/'pay' and 'costs'/'cost' match."""
    for suffix in ("ments", "ment", "ing", "ies", "es", "ed", "s"):
        if token.endswith(suffix) and len(token) - len(suffix) >= 3:
            return token[: -len(suffix)] + ("y" if suffix == "ies" else "")
    return token


def tokenize(text: str) -> list[str]:
    return [_stem(t) for t in _TOKEN.findall(text.lower()) if t not in STOPWORDS]


def _clean(lines: list[str]) -> str:
    text = "\n".join(lines).strip()
    text = text.replace("**", "").replace("`", "")
    return re.sub(r"\n{3,}", "\n\n", text)


def parse_guide(markdown: str) -> tuple[str, list[Chunk]]:
    """Return (document_id, chunks)."""
    doc_id_match = _DOC_ID.search(markdown)
    document_id = doc_id_match.group(1) if doc_id_match else "UNKNOWN"

    chunks: list[Chunk] = []
    section_id: str | None = None
    section_title: str | None = None
    sub_id: str | None = None
    sub_title: str | None = None
    buffer: list[str] = []
    section_has_subsections = False

    def flush() -> None:
        sec_id, sec_title, s_id, s_title = section_id, section_title, sub_id, sub_title
        if sec_id is None or sec_title is None:
            return
        text = _clean(buffer)
        if s_id is not None and s_title is not None:
            chunks.append(Chunk(s_id, s_title, sec_title, text))
        elif not section_has_subsections and text:
            chunks.append(Chunk(sec_id, sec_title, sec_title, text))

    for line in markdown.splitlines():
        if m := _SECTION.match(line):
            flush()
            section_id, section_title = m.group(1), m.group(2)
            sub_id = sub_title = None
            section_has_subsections = False
            buffer = []
        elif m := _SUBSECTION.match(line):
            if sub_id is None:
                # Text between a ## heading and its first ### is dropped (none in the guide).
                section_has_subsections = True
            flush()
            sub_id, sub_title = m.group(1), m.group(2)
            buffer = []
        elif section_id is not None:
            buffer.append(line)
    flush()
    return document_id, chunks


@dataclass(frozen=True)
class SearchHit:
    chunk: Chunk
    score: float


class GuideIndex:
    def __init__(self, document_name: str, document_id: str, chunks: list[Chunk]):
        if not chunks:
            raise ValueError("no sections found in the billing guide")
        self.document_name = document_name
        self.document_id = document_id
        self.chunks = chunks
        # Heading words are indexed together with the body (twice, to weight titles).
        corpus = [
            tokenize(f"{c.parent_heading} {c.heading} {c.heading} {c.text}") for c in chunks
        ]
        self._bm25 = BM25Okapi(corpus)

    @classmethod
    def from_file(cls, path: Path = DEFAULT_GUIDE) -> GuideIndex:
        document_id, chunks = parse_guide(path.read_text(encoding="utf-8"))
        return cls(path.name, document_id, chunks)

    def search(self, query: str, top_k: int = 3) -> list[SearchHit]:
        tokens = tokenize(query)
        if not tokens:
            return []
        scores = self._bm25.get_scores(tokens)
        ranked = sorted(range(len(self.chunks)), key=lambda i: scores[i], reverse=True)
        return [SearchHit(self.chunks[i], float(scores[i])) for i in ranked[:top_k] if scores[i] > 0]
