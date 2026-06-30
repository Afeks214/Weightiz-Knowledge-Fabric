from __future__ import annotations

from dataclasses import dataclass

from wzkf.storage.hashing import sha256_text


@dataclass(frozen=True)
class ParentChunk:
    id: str
    document_id: str
    chunk_index: int
    text: str
    token_count: int
    chunk_hash: str
    section_title: str | None = None


@dataclass(frozen=True)
class ChildChunk:
    id: str
    parent_chunk_id: str
    document_id: str
    child_index: int
    text: str
    token_count: int
    chunk_hash: str


@dataclass(frozen=True)
class ChunkingResult:
    parent_chunks: list[ParentChunk]
    child_chunks: list[ChildChunk]


class ParentChildChunker:
    def __init__(self, parent_token_target: int = 1200, child_token_target: int = 250):
        self.parent_token_target = parent_token_target
        self.child_token_target = child_token_target

    def chunk(self, document_id: str, text: str, section_title: str | None = None) -> ChunkingResult:
        normalized = text.strip()
        if not normalized:
            return ChunkingResult(parent_chunks=[], child_chunks=[])

        parent = self._make_parent(document_id, 0, normalized, section_title)
        children = self._make_children(parent)
        return ChunkingResult(parent_chunks=[parent], child_chunks=children)

    def _make_parent(
        self,
        document_id: str,
        index: int,
        text: str,
        section_title: str | None,
    ) -> ParentChunk:
        chunk_hash = sha256_text(text)
        return ParentChunk(
            id=sha256_text(f"{document_id}:parent:{index}:{chunk_hash}")[:24],
            document_id=document_id,
            chunk_index=index,
            text=text,
            token_count=_token_count(text),
            chunk_hash=chunk_hash,
            section_title=section_title,
        )

    def _make_children(self, parent: ParentChunk) -> list[ChildChunk]:
        segments = _atomic_segments(parent.text)
        grouped: list[str] = []
        current: list[str] = []
        current_tokens = 0

        for segment in segments:
            tokens = _token_count(segment)
            if current and current_tokens + tokens > self.child_token_target:
                grouped.append("\n".join(current).strip())
                current = []
                current_tokens = 0
            current.append(segment)
            current_tokens += tokens

        if current:
            grouped.append("\n".join(current).strip())

        children: list[ChildChunk] = []
        for index, child_text in enumerate(grouped):
            chunk_hash = sha256_text(child_text)
            children.append(
                ChildChunk(
                    id=sha256_text(f"{parent.id}:child:{index}:{chunk_hash}")[:24],
                    parent_chunk_id=parent.id,
                    document_id=parent.document_id,
                    child_index=index,
                    text=child_text,
                    token_count=_token_count(child_text),
                    chunk_hash=chunk_hash,
                )
            )
        return children


def _token_count(text: str) -> int:
    return len(text.split())


def _atomic_segments(text: str) -> list[str]:
    lines = text.splitlines()
    segments: list[str] = []
    buffer: list[str] = []
    in_fence = False
    fence_marker = ""

    for line in lines:
        stripped = line.strip()
        starts_fence = stripped.startswith("```") or stripped == "$$"
        if starts_fence and not in_fence:
            if buffer:
                segments.extend(_word_segments("\n".join(buffer)))
                buffer = []
            in_fence = True
            fence_marker = "$$" if stripped == "$$" else "```"
            buffer.append(line)
            continue

        if in_fence:
            buffer.append(line)
            if (fence_marker == "$$" and stripped == "$$") or (
                fence_marker == "```" and stripped.startswith("```") and len(buffer) > 1
            ):
                segments.append("\n".join(buffer).strip())
                buffer = []
                in_fence = False
                fence_marker = ""
            continue

        if stripped:
            buffer.append(line)
        elif buffer:
            segments.extend(_word_segments("\n".join(buffer)))
            buffer = []

    if buffer:
        if in_fence:
            segments.append("\n".join(buffer).strip())
        else:
            segments.extend(_word_segments("\n".join(buffer)))

    return [segment for segment in segments if segment.strip()]


def _word_segments(text: str) -> list[str]:
    words = text.split()
    return [" ".join(words)] if words else []
