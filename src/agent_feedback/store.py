"""
In-memory (+ optional JSON persistence) feedback store.
Thread-safe.
"""

from __future__ import annotations
import json
import os
import threading
from collections import defaultdict
from typing import Any, Dict, List, Optional

from .models import Feedback, FeedbackType, ApprovalStatus


class FeedbackStore:
    """Thread-safe store for agent feedback records.

    Usage::

        store = FeedbackStore()
        fb = Feedback(FeedbackType.REJECTION, agent_output="wrong answer")
        store.save(fb)
        rejections = store.query(status=ApprovalStatus.REJECTED)
    """

    def __init__(self, persist_path: Optional[str] = None) -> None:
        self._records: Dict[str, Feedback] = {}
        self._lock = threading.Lock()
        self._persist_path = persist_path
        if persist_path and os.path.exists(persist_path):
            self._load(persist_path)

    def save(self, feedback: Feedback) -> str:
        """Persist a feedback record. Returns its id."""
        with self._lock:
            self._records[feedback.id] = feedback
        if self._persist_path:
            self._flush()
        return feedback.id

    def get(self, feedback_id: str) -> Optional[Feedback]:
        return self._records.get(feedback_id)

    def delete(self, feedback_id: str) -> bool:
        with self._lock:
            if feedback_id in self._records:
                del self._records[feedback_id]
                return True
        return False

    def all(self) -> List[Feedback]:
        return list(self._records.values())

    def query(
        self,
        feedback_type: Optional[FeedbackType] = None,
        status: Optional[ApprovalStatus] = None,
        session_id: Optional[str] = None,
        tags: Optional[List[str]] = None,
        min_rating: Optional[float] = None,
        limit: Optional[int] = None,
    ) -> List[Feedback]:
        """Filter feedback records by criteria."""
        results = list(self._records.values())
        if feedback_type is not None:
            results = [r for r in results if r.feedback_type == feedback_type]
        if status is not None:
            results = [r for r in results if r.status == status]
        if session_id is not None:
            results = [r for r in results if r.session_id == session_id]
        if tags:
            results = [r for r in results if any(t in r.tags for t in tags)]
        if min_rating is not None:
            results = [r for r in results if r.rating is not None and r.rating >= min_rating]
        results.sort(key=lambda r: r.timestamp, reverse=True)
        if limit:
            results = results[:limit]
        return results

    def stats(self) -> Dict[str, Any]:
        """Return aggregate statistics over stored feedback."""
        all_fb = self.all()
        if not all_fb:
            return {"total": 0}
        by_type: Dict[str, int] = defaultdict(int)
        by_status: Dict[str, int] = defaultdict(int)
        ratings = [f.rating for f in all_fb if f.rating is not None]
        corrections = [f for f in all_fb if f.was_corrected]
        for f in all_fb:
            by_type[f.feedback_type.value] += 1
            by_status[f.status.value] += 1
        return {
            "total": len(all_fb),
            "by_type": dict(by_type),
            "by_status": dict(by_status),
            "avg_rating": sum(ratings) / len(ratings) if ratings else None,
            "correction_rate": len(corrections) / len(all_fb),
        }

    def clear(self) -> None:
        with self._lock:
            self._records.clear()

    def _flush(self) -> None:
        data = [f.to_dict() for f in self._records.values()]
        with open(self._persist_path, "w") as fp:  # type: ignore
            json.dump(data, fp, indent=2)

    def _load(self, path: str) -> None:
        with open(path) as fp:
            data = json.load(fp)
        for item in data:
            fb = Feedback.from_dict(item)
            self._records[fb.id] = fb
