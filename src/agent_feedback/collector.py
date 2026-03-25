"""
FeedbackCollector: high-level API for capturing corrections and ratings.
"""

from __future__ import annotations
from typing import Any, Dict, List, Optional

from .models import Feedback, FeedbackType, ApprovalStatus
from .store import FeedbackStore


class FeedbackCollector:
    """Collect corrections, ratings, and comments on agent outputs.

    Usage::

        collector = FeedbackCollector(session_id="session-001")
        collector.correction("The sky is green", "The sky is blue")
        collector.rate("Good summary", 4.5)
        report = collector.report()
    """

    def __init__(
        self,
        session_id: Optional[str] = None,
        store: Optional[FeedbackStore] = None,
    ) -> None:
        self.session_id = session_id
        self._store = store or FeedbackStore()

    def correction(
        self,
        agent_output: Any,
        corrected_output: Any,
        comment: str = "",
        tags: Optional[List[str]] = None,
    ) -> Feedback:
        """Record a human correction to an agent output."""
        fb = Feedback(
            feedback_type=FeedbackType.CORRECTION,
            agent_output=agent_output,
            status=ApprovalStatus.REJECTED,
            corrected_output=corrected_output,
            comment=comment,
            tags=tags or [],
            session_id=self.session_id,
        )
        self._store.save(fb)
        return fb

    def rate(
        self,
        agent_output: Any,
        rating: float,
        comment: str = "",
        tags: Optional[List[str]] = None,
    ) -> Feedback:
        """Record a numeric rating (0-10) for an agent output."""
        if not 0.0 <= rating <= 10.0:
            raise ValueError("rating must be in [0, 10]")
        fb = Feedback(
            feedback_type=FeedbackType.RATING,
            agent_output=agent_output,
            status=ApprovalStatus.APPROVED if rating >= 3.0 else ApprovalStatus.REJECTED,
            rating=rating,
            comment=comment,
            tags=tags or [],
            session_id=self.session_id,
        )
        self._store.save(fb)
        return fb

    def comment(
        self,
        agent_output: Any,
        comment: str,
        tags: Optional[List[str]] = None,
    ) -> Feedback:
        """Attach a free-text comment to an agent output."""
        fb = Feedback(
            feedback_type=FeedbackType.COMMENT,
            agent_output=agent_output,
            status=ApprovalStatus.PENDING,
            comment=comment,
            tags=tags or [],
            session_id=self.session_id,
        )
        self._store.save(fb)
        return fb

    def reject(
        self,
        agent_output: Any,
        reason: str = "",
        tags: Optional[List[str]] = None,
    ) -> Feedback:
        """Explicitly reject an agent output."""
        fb = Feedback(
            feedback_type=FeedbackType.REJECTION,
            agent_output=agent_output,
            status=ApprovalStatus.REJECTED,
            comment=reason,
            tags=tags or [],
            session_id=self.session_id,
        )
        self._store.save(fb)
        return fb

    def report(self) -> Dict[str, Any]:
        """Return a summary of collected feedback for this session."""
        kwargs: Dict[str, Any] = {}
        if self.session_id:
            kwargs["session_id"] = self.session_id
        records = self._store.query(**kwargs)
        return {
            "session_id": self.session_id,
            "total": len(records),
            "stats": self._store.stats(),
            "records": [r.to_dict() for r in records],
        }
