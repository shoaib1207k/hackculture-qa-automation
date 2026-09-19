"""Behaviour measurements, computed from transcript timestamps. No LLM."""

import logging

from ...models import TranscriptSegment

logger = logging.getLogger(__name__)


DEAD_AIR_THRESHOLD_S = 10.0
MAX_INTERRUPTIONS = 2


def compute_dead_air(segments: list[TranscriptSegment], threshold_s: float = DEAD_AIR_THRESHOLD_S
                     ) -> tuple[bool, float, list[str]]:
    """Returns (flagged, longest_gap_seconds, [segment_ids bounding the gap])."""
    ordered = sorted(segments, key=lambda s: s.start)
    longest, ids = 0.0, []
    for a, b in zip(ordered, ordered[1:]):
        if b.start - a.end > longest:
            longest, ids = b.start - a.end, [a.segment_id, b.segment_id]
    logger.debug("compute_dead_air longest=%.1fs threshold=%.0fs between=%s", longest, threshold_s, ids)
    return longest > threshold_s, longest, ids


def compute_interruptions(segments: list[TranscriptSegment]) -> tuple[int, list[str]]:
    """Counts adjacent, different-speaker segments that overlap in time."""
    ordered = sorted(segments, key=lambda s: s.start)
    count, ids = 0, []
    for a, b in zip(ordered, ordered[1:]):
        if a.speaker != b.speaker and b.start < a.end:
            count += 1
            ids += [a.segment_id, b.segment_id]
    logger.debug("compute_interruptions count=%d ids=%s", count, ids)
    return count, ids
