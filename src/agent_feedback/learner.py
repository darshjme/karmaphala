"""
RejectionLearner: extract patterns from rejections to improve future prompts.
"""

from __future__ import annotations
from collections import Counter
from typing import Any, Dict, List, Tuple

from .models import Feedback, FeedbackType, ApprovalStatus
from .store import FeedbackStore


class RejectionLearner:
    """Analyze rejection feedback to surface common failure patterns.

    Usage::

        learner = RejectionLearner(store)
        patterns = learner.top_rejection_tags(n=5)
        summary = learner.rejection_summary()
        addendum = learner.build_system_prompt_addendum()
    """

    def __init__(self, store: FeedbackStore) -> None:
        self._store = store

    def _rejections(self) -> List[Feedback]:
        return self._store.query(status=ApprovalStatus.REJECTED)

    def top_rejection_tags(self, n: int = 10) -> List[Tuple[str, int]]:
        """Return the most common tags among rejected feedback."""
        tag_counts: Counter = Counter()
        for fb in self._rejections():
            tag_counts.update(fb.tags)
        return tag_counts.most_common(n)

    def correction_pairs(self) -> List[Tuple[Any, Any]]:
        """Return (agent_output, corrected_output) pairs from corrections."""
        corrections = self._store.query(feedback_type=FeedbackType.CORRECTION)
        return [(f.agent_output, f.corrected_output) for f in corrections if f.was_corrected]

    def rejection_summary(self) -> Dict[str, Any]:
        """High-level summary of what the agent gets wrong most often."""
        rejections = self._rejections()
        corrections = self.correction_pairs()
        top_tags = self.top_rejection_tags()
        comments = [f.comment for f in rejections if f.comment]
        return {
            "total_rejections": len(rejections),
            "with_corrections": len(corrections),
            "top_failure_tags": top_tags,
            "sample_comments": comments[:10],
            "correction_pairs_sample": corrections[:5],
        }

    def build_system_prompt_addendum(self) -> str:
        """Generate a 'lessons learned' block to prepend to future prompts."""
        summary = self.rejection_summary()
        lines = ["# Learned from past rejections:"]
        if summary["top_failure_tags"]:
            lines.append(
                "Common failure areas: "
                + ", ".join(t for t, _ in summary["top_failure_tags"])
            )
        for orig, corrected in summary["correction_pairs_sample"]:
            lines.append(f"- Instead of: {orig!r}")
            lines.append(f"  Use: {corrected!r}")
        return "\n".join(lines)
