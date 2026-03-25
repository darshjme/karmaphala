"""
Approval gates: block agent execution until a human approves (or times out).
"""

from __future__ import annotations
import threading
from typing import Any, Callable, Dict, List, Optional

from .models import Feedback, FeedbackType, ApprovalStatus
from .store import FeedbackStore


class ApprovalGate:
    """Synchronous approval gate for agent actions.

    Usage (with reviewer callback)::

        gate = ApprovalGate(timeout=30.0)
        gate.set_reviewer(lambda fb: fb.agent_output != "bad")
        status = gate.request_approval("some agent output")
        # ApprovalStatus.APPROVED or REJECTED
    """

    def __init__(
        self,
        timeout: float = 60.0,
        store: Optional[FeedbackStore] = None,
    ) -> None:
        self.timeout = timeout
        self._store = store or FeedbackStore()
        self._reviewer: Optional[Callable[[Feedback], bool]] = None
        self._pending: Dict[str, Feedback] = {}
        self._events: Dict[str, threading.Event] = {}
        self._lock = threading.Lock()

    def set_reviewer(self, fn: Callable[[Feedback], bool]) -> None:
        """Set a callable that receives a Feedback and returns True=approve."""
        self._reviewer = fn

    def request_approval(
        self,
        agent_output: Any,
        context: Optional[dict] = None,
        tags: Optional[list] = None,
    ) -> ApprovalStatus:
        """Block until reviewed or timeout. Returns final ApprovalStatus."""
        fb = Feedback(
            feedback_type=FeedbackType.APPROVAL,
            agent_output=agent_output,
            context=context or {},
            tags=tags or [],
        )
        self._store.save(fb)

        if self._reviewer is not None:
            approved = self._reviewer(fb)
            fb.status = ApprovalStatus.APPROVED if approved else ApprovalStatus.REJECTED
            self._store.save(fb)
            return fb.status

        # Async wait path
        event = threading.Event()
        with self._lock:
            self._pending[fb.id] = fb
            self._events[fb.id] = event

        signaled = event.wait(timeout=self.timeout)
        with self._lock:
            self._pending.pop(fb.id, None)
            self._events.pop(fb.id, None)

        if not signaled:
            fb.status = ApprovalStatus.TIMEOUT
            self._store.save(fb)
        return fb.status

    def respond(self, feedback_id: str, approved: bool, comment: str = "") -> bool:
        """External responder approves or rejects a pending gate."""
        with self._lock:
            fb = self._pending.get(feedback_id)
            event = self._events.get(feedback_id)
        if fb is None:
            return False
        fb.status = ApprovalStatus.APPROVED if approved else ApprovalStatus.REJECTED
        fb.comment = comment
        self._store.save(fb)
        if event:
            event.set()
        return True

    @property
    def pending_ids(self) -> List[str]:
        with self._lock:
            return list(self._pending.keys())


class AsyncApprovalGate:
    """Non-blocking approval gate for async/event-driven agent frameworks."""

    def __init__(self, store: Optional[FeedbackStore] = None) -> None:
        self._store = store or FeedbackStore()
        self._lock = threading.Lock()

    def submit(self, agent_output: Any, context: Optional[dict] = None) -> Feedback:
        """Submit output for async approval. Returns Feedback in PENDING state."""
        fb = Feedback(
            feedback_type=FeedbackType.APPROVAL,
            agent_output=agent_output,
            context=context or {},
        )
        self._store.save(fb)
        return fb

    def decide(self, feedback_id: str, approved: bool, comment: str = "") -> bool:
        """Record a decision for a previously submitted item."""
        fb = self._store.get(feedback_id)
        if fb is None:
            return False
        fb.status = ApprovalStatus.APPROVED if approved else ApprovalStatus.REJECTED
        fb.comment = comment
        self._store.save(fb)
        return True

    def pending(self) -> List[Feedback]:
        return self._store.query(status=ApprovalStatus.PENDING)
