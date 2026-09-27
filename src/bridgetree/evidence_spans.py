"""Deterministic, exact source spans and conservative premise accounting.

Offsets always index ``Memory.text`` in Python characters.  Source roles come
only from validated metadata, never from role-looking strings in the text.
Neither source grounding nor the premise count proves semantic support.
"""

from __future__ import annotations

import hashlib
import json
import re
from typing import Any, Mapping, Sequence

from .types import Memory


class SourceSpanValidationError(ValueError):
    """Authoritative source metadata cannot safely ground an evidence span."""


def _digest(value: Any) -> str:
    return hashlib.sha256(
        json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()


def source_segments(memory: Memory) -> list[dict]:
    """Validate authoritative segments and fill every structural gap as unknown.

    Segment order, offsets, roles and message indices follow the v1 validation
    contract.  An absent metadata field is legacy unknown provenance; an empty
    authoritative list still leaves all characters unknown.  Empty segments
    are valid metadata but contribute no characters.
    """
    raw = memory.metadata.get("source_segments")
    if raw is None:
        return [{"role": "unknown", "start": 0, "end": len(memory.text),
                 "source_message_indices": [], "provenance": "legacy_unknown"}]
    if not isinstance(raw, list):
        raise SourceSpanValidationError("source_segments must be a list")
    segments = []
    previous_end = 0
    for segment in raw:
        if not isinstance(segment, dict):
            raise SourceSpanValidationError("source segment must be an object")
        start, end = segment.get("start"), segment.get("end")
        if (
            isinstance(start, bool) or not isinstance(start, int)
            or isinstance(end, bool) or not isinstance(end, int)
            or not previous_end <= start <= end <= len(memory.text)
        ):
            raise SourceSpanValidationError("invalid authoritative source segment offsets")
        role = segment.get("role")
        if not isinstance(role, str) or not role.strip():
            raise SourceSpanValidationError("source segment role must be a nonempty string")
        indices = segment.get("source_message_indices")
        if not isinstance(indices, list):
            raise SourceSpanValidationError("source message indices must be a list")
        if any(isinstance(index, bool) or not isinstance(index, int) or index < 0 for index in indices):
            raise SourceSpanValidationError("invalid source message indices")
        if start > previous_end:
            segments.append({"role": "unknown", "start": previous_end, "end": start,
                             "source_message_indices": [], "provenance": "unknown_gap"})
        if end > start:
            segments.append({"role": role, "start": start, "end": end,
                             "source_message_indices": list(indices), "provenance": "authoritative"})
        previous_end = end
    if previous_end < len(memory.text) or not segments:
        segments.append({"role": "unknown", "start": previous_end, "end": len(memory.text),
                         "source_message_indices": [], "provenance": "unknown_gap"})
    return segments


# This is a deterministic formatting boundary, not a linguistic claim.  Avoid
# treating a decimal point or an embedded URL dot as an English sentence end.
_BOUNDARY = re.compile(r'[。！？]+[”’"\')）\]]*[ \t]*|[.!?]+[”’"\')）\]]*(?=\s|$)[ \t]*|\r?\n+')


def _sentence_ranges(text: str, start: int, end: int) -> list[tuple[int, int]]:
    ranges = []
    cursor = start
    for match in _BOUNDARY.finditer(text, start, end):
        right = match.end()
        if right > cursor:
            ranges.append((cursor, right))
            cursor = right
    if cursor < end:
        ranges.append((cursor, end))
    return ranges or [(start, end)]


def source_units(memory: Memory, max_chars: int) -> list[dict]:
    """Partition the complete source into bounded, stable, nonoverlapping spans.

    Pack complete sentences when they fit; split an overlong sentence only when
    necessary.  Forced pieces share a ``premise_group_ids`` entry so that a
    downstream model cannot turn one sentence into multiple independent
    premises merely by assessing its pieces separately.  IDs depend on source
    identity, content and positions, never on model requests or batch order.
    """
    if isinstance(max_chars, bool) or not isinstance(max_chars, int) or max_chars < 1:
        raise ValueError("max_chars must be a positive integer")
    segments = source_segments(memory)
    source_hash = hashlib.sha256(memory.text.encode("utf-8")).hexdigest()
    identity = [memory.memory_id, memory.source_id, source_hash]
    units = []
    for segment in segments:
        pending_start = segment["start"]
        pending_end = pending_start
        pending_groups: list[str] = []

        def emit(left: int, right: int, groups: list[str], segment=segment) -> None:
            span_id = "s_" + _digest([*identity, segment, left, right])[:16]
            units.append({
                "unit_id": span_id, "span_id": span_id,
                "memory_id": memory.memory_id, "source_id": memory.source_id,
                "observation_order": memory.timestamp, "time_metadata": memory.time_metadata,
                "source_hash": source_hash, "start": left, "end": right,
                "text": memory.text[left:right], "role": segment["role"],
                "source_message_indices": list(segment["source_message_indices"]),
                "provenance": segment["provenance"], "source_segments": [dict(segment)],
                "premise_group_ids": list(groups),
            })

        for left, right in _sentence_ranges(memory.text, segment["start"], segment["end"]):
            group = "p_" + _digest([*identity, segment, left, right])[:16]
            if right - left > max_chars:
                if pending_groups:
                    emit(pending_start, pending_end, pending_groups)
                    pending_groups = []
                for chunk_start in range(left, right, max_chars):
                    emit(chunk_start, min(right, chunk_start + max_chars), [group])
                pending_start = pending_end = right
            else:
                if pending_groups and right - pending_start > max_chars:
                    emit(pending_start, pending_end, pending_groups)
                    pending_groups = []
                if not pending_groups:
                    pending_start = left
                pending_end = right
                pending_groups.append(group)
        if pending_groups:
            emit(pending_start, pending_end, pending_groups)
    for index, unit in enumerate(units):
        unit["previous_span_id"] = units[index - 1]["span_id"] if index else None
        unit["next_span_id"] = units[index + 1]["span_id"] if index + 1 < len(units) else None
    return units


def independent_premise_count(facts: Sequence[Mapping[str, Any]]) -> int:
    """Count provenance-disjoint groups of validated support/partial facts.

    One assessment is one premise even when it contains several fragments.
    Assessments that share an ID, source range or original sentence group are
    conservatively merged transitively.  This may undercount distinct claims
    drawn from a broad shared source; it never certifies semantic independence.
    Malformed or absent source coordinates cannot establish a premise.

    New facts store ``fragments`` with start/end and ``premise_group_ids``.
    ``quote_occurrences`` is supported for already validated v1 artifacts.
    """
    premises = []
    for fact in facts:
        if fact.get("relation") not in {"partial", "support"}:
            continue
        memory_id = fact.get("memory_id")
        if not isinstance(memory_id, str) or not memory_id:
            continue
        fragments = fact.get("fragments", fact.get("quote_occurrences", []))
        if not isinstance(fragments, (list, tuple)):
            continue
        ranges = []
        groups = set(fact.get("premise_group_ids", []))
        for fragment in fragments:
            if not isinstance(fragment, Mapping):
                continue
            left, right = fragment.get("start"), fragment.get("end")
            if (
                isinstance(left, bool) or not isinstance(left, int)
                or isinstance(right, bool) or not isinstance(right, int)
                or not 0 <= left < right
            ):
                continue
            ranges.append((left, right))
            groups.update(fragment.get("premise_group_ids", []))
        if ranges:
            premises.append((memory_id, fact.get("assessment_id"), ranges, groups))

    parents = list(range(len(premises)))

    def root(index: int) -> int:
        while parents[index] != index:
            parents[index] = parents[parents[index]]
            index = parents[index]
        return index

    for index, (memory, assessment, ranges, groups) in enumerate(premises):
        for other in range(index):
            old_memory, old_assessment, old_ranges, old_groups = premises[other]
            same_assessment = bool(assessment and assessment == old_assessment)
            same_source = memory == old_memory and (
                bool(groups & old_groups)
                or any(left < old_right and old_left < right
                       for left, right in ranges for old_left, old_right in old_ranges)
            )
            if same_assessment or same_source:
                parents[root(index)] = root(other)
    return len({root(index) for index in range(len(premises))})
