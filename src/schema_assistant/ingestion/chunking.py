from __future__ import annotations


def chunk_text(text: str, *, max_chars: int, overlap_chars: int) -> list[str]:
    if max_chars <= 0:
        raise ValueError("max_chars must be positive")
    if overlap_chars < 0 or overlap_chars >= max_chars:
        raise ValueError("overlap_chars must be lower than max_chars")

    normalized = "\n".join(line.rstrip() for line in text.splitlines()).strip()
    if not normalized:
        return []

    paragraphs = [part.strip() for part in normalized.split("\n\n") if part.strip()]
    chunks: list[str] = []
    current = ""

    for paragraph in paragraphs:
        if len(paragraph) > max_chars:
            if current:
                chunks.append(current.strip())
                current = ""
            chunks.extend(
                _split_long_text(paragraph, max_chars=max_chars, overlap_chars=overlap_chars)
            )
            continue

        candidate = f"{current}\n\n{paragraph}".strip() if current else paragraph
        if len(candidate) <= max_chars:
            current = candidate
            continue

        chunks.append(current.strip())
        current = _with_overlap(current, paragraph, overlap_chars)

    if current:
        chunks.append(current.strip())

    return [chunk for chunk in chunks if chunk]


def _split_long_text(text: str, *, max_chars: int, overlap_chars: int) -> list[str]:
    chunks = []
    start = 0
    while start < len(text):
        end = min(start + max_chars, len(text))
        chunks.append(text[start:end].strip())
        if end == len(text):
            break
        start = max(0, end - overlap_chars)
    return [chunk for chunk in chunks if chunk]


def _with_overlap(previous: str, next_paragraph: str, overlap_chars: int) -> str:
    if overlap_chars == 0:
        return next_paragraph
    overlap = previous[-overlap_chars:].strip()
    return f"{overlap}\n\n{next_paragraph}".strip() if overlap else next_paragraph
